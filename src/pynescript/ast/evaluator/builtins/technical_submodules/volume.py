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

"""Volume-based Technical Indicators."""

from __future__ import annotations

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import QUINARY
from .core import TERNARY
from .core import UNARY
from .core import TechnicalHelpers


class VolumeIndicators(TechnicalHelpers):
    """Volume-based technical indicators: OBV, MFI, CMF, WAD, WVAD, EMV, Klinger, APO, VPT."""

    # -- Public API (builtin_ta_ prefix) ------------------------------------

    def _builtin_ta_obv(self, args: list[Any]) -> Any:
        """On-Balance Volume.

        Forms:
        - ``ta.obv`` / ``ta.obv()`` — chart close + volume
        - ``ta.obv(close, volume)`` — explicit series
        """
        msg = "ta.obv expects close and volume series (or no args)"
        if len(args) == 0:
            closes = self._context_series("close")
            volumes = self._context_series("volume")
            if not volumes:
                volumes = [0.0] * len(closes)
        elif len(args) == BINARY:
            closes = self._expect_list(args[0], msg)
            volumes = self._expect_list(args[1], msg)
        else:
            self._error(msg)
            return None
        if not closes:
            return None
        n = min(len(closes), len(volumes)) if volumes else 0
        if n == 0:
            return None
        # _obv returns the current cumulative scalar (bar-mode friendly)
        return self._obv(closes[-n:], volumes[-n:])

    def _builtin_ta_mfi(self, args: list[Any]) -> float | None:
        """Money Flow Index.

        Forms:
        - ``ta.mfi(length)`` / bare ``mfi(length)`` — hlc3 + volume from context
        - ``ta.mfi(source, length)`` — source as typical price + context volume
        - legacy 5-arg HLC+volume+length
        """
        if len(args) == UNARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.mfi length must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            volumes = self._context_series("volume") or [0.0] * len(closes)
            n = min(len(highs), len(lows), len(closes), len(volumes))
            if n == 0:
                return None
            return self._mfi(highs[-n:], lows[-n:], closes[-n:], volumes[-n:], length)
        if len(args) == BINARY:
            series = self._as_series(args[0])
            length = self._expect_int(args[1], "ta.mfi length must be int")
            volumes = self._context_series("volume")
            if not volumes:
                volumes = [0.0] * len(series)
            n = min(len(series), len(volumes))
            if n == 0:
                return None
            series = series[-n:]
            volumes = volumes[-n:]
            return self._mfi(series, series, series, volumes, length)
        msg = "ta.mfi expects source, length (or high, low, close, volume, length)"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        volumes = self._expect_list(args[3], msg)
        length = self._expect_int(args[4], msg)
        return self._mfi(highs, lows, closes, volumes, length)

    def _builtin_ta_accdist(self, args: list[Any]) -> Any:
        """Accumulation/Distribution Index.

        TV: ``ta.accdist`` / ``ta.accdist()`` with no args uses H/L/C/V context.
        """
        if len(args) == 0:
            high_series = self._context_series("high")
            low_series = self._context_series("low")
            close_series = self._context_series("close")
            volume_series = self._context_series("volume")
        elif len(args) >= QUATERNARY:
            high_series = self._as_series(args[0])
            low_series = self._as_series(args[1])
            close_series = self._as_series(args[2])
            volume_series = self._as_series(args[3])
        else:
            self._error("ta.accdist() requires 0 or 4 arguments: high, low, close, volume")
            return None

        return self._finalize_series(self._accdist(high_series, low_series, close_series, volume_series))

    def _builtin_ta_wad(self, args: list[Any]) -> list[float | None]:
        """Williams Accumulation/Distribution - volume accumulation index.

        Forms:
        - ``ta.wad`` / ``ta.wad()`` — chart high/low/close/volume
        - ``ta.wad(high, low, close, volume)`` — explicit series
        """
        if len(args) == 0:
            high_series = self._context_series("high")
            low_series = self._context_series("low")
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
        elif len(args) >= QUATERNARY:
            high_series = self._as_series(args[0])
            low_series = self._as_series(args[1])
            close_series = self._as_series(args[2])
            volume_series = self._as_series(args[3])
        else:
            self._error("ta.wad() requires 0 or 4 arguments: high, low, close, volume")
            return []

        return self._wad(high_series, low_series, close_series, volume_series)

    def _builtin_ta_wvad(self, args: list[Any]) -> list[float | None]:
        """Williams Volume Accumulation/Distribution - normalized WAD.

        Forms:
        - ``ta.wvad(period)`` — H/L/C/V from context
        - ``ta.wvad(high, low, close, volume, period?)``
        """
        if len(args) == UNARY and self._is_period_like(args[0]):
            period = self._expect_int(args[0], "period must be integer")
            high_series = self._context_series("high")
            low_series = self._context_series("low")
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
            return self._wvad(high_series, low_series, close_series, volume_series, period)
        if len(args) == 0:
            high_series = self._context_series("high")
            low_series = self._context_series("low")
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
            return self._wvad(high_series, low_series, close_series, volume_series, 20)
        if len(args) < QUATERNARY:
            self._error("ta.wvad() requires 0, 1, or 4+ arguments: [high, low, close, volume,] period")
            return []

        high_series = self._as_series(args[0])
        low_series = self._as_series(args[1])
        close_series = self._as_series(args[2])
        volume_series = self._as_series(args[3])
        period_arg_idx = QUATERNARY
        default_period = 20
        period = (
            self._expect_int(args[period_arg_idx], "period must be integer")
            if len(args) > period_arg_idx
            else default_period
        )

        return self._wvad(high_series, low_series, close_series, volume_series, period)

    def _builtin_ta_cmf(self, args: list[Any]) -> list[float | None]:
        """Chaikin Money Flow indicator.

        Forms:
        - ``ta.cmf(period)`` — H/L/C/V from chart context
        - ``ta.cmf(close, high, low, volume, period)`` — explicit series
        """
        if len(args) == UNARY and self._is_period_like(args[0]):
            period = self._expect_int(args[0], "ta.cmf period must be integer")
            high_series = self._context_series("high")
            low_series = self._context_series("low")
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
            return self._cmf(close_series, high_series, low_series, volume_series, period)
        if len(args) < QUINARY:
            self._error(
                "ta.cmf() requires 1 argument (period) or 5: close, high, low, volume, period"
            )
            return []

        close_series = self._as_series(args[0])
        high_series = self._as_series(args[1])
        low_series = self._as_series(args[2])
        volume_series = self._as_series(args[3])
        period = self._expect_int(args[4], "ta.cmf period must be integer")

        return self._cmf(close_series, high_series, low_series, volume_series, period)

    def _builtin_ta_klinger(self, args: list[Any]) -> list[float | None]:
        """Klinger Oscillator.

        ta.klinger(high, low, close, volume, fast_period, slow_period)
        Volume-based momentum oscillator.
        Returns KO series.
        """
        senary = 6
        if len(args) < senary:
            msg = "ta.klinger() requires 6 arguments: high, low, close, volume, fast_period, slow_period"
            self._error(msg)

        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        volume_series = args[3] if isinstance(args[3], list) else [args[3]]
        fast_period = self._expect_int(args[4], "ta.klinger fast_period must be integer")
        slow_period = self._expect_int(args[5], "ta.klinger slow_period must be integer")

        return self._klinger(close_series, volume_series, fast_period, slow_period)

    def _builtin_ta_apo(self, args: list[Any]) -> list[float | None]:
        """Absolute Price Oscillator.

        ta.apo(series, fast_period, slow_period)
        APO = EMA(fast) - EMA(slow)
        Returns APO series.
        """
        if len(args) < TERNARY:
            msg = "ta.apo() requires 3 arguments: series, fast_period, slow_period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        fast = self._expect_int(args[1], "ta.apo fast_period must be integer")
        slow = self._expect_int(args[2], "ta.apo slow_period must be integer")

        return self._apo(series, fast, slow)

    def _builtin_ta_vpt(self, args: list[Any]) -> float | None:
        """Volume Price Trend.

        ta.vpt(series)
        Combines volume and price direction.
        """
        unary = 1
        if len(args) < unary:
            msg = "ta.vpt() requires 1 argument: series"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        closes = (getattr(self, "current_series", None) or {}).get("close", [])
        volumes = (getattr(self, "current_series", None) or {}).get("volume", [])

        if not closes or not volumes or len(series) < BINARY:
            return None

        return self._vpt(closes, volumes)

    def _builtin_ta_emv(self, args: list[Any]) -> float | None:
        """Ease of Movement.

        ta.emv(length)
        Measures ease of price movement relative to volume.
        """
        unary = 1
        if len(args) < unary:
            msg = "ta.emv() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < unary:
            msg = "EMV length must be >= 1"
            self._error(msg)

        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])
        volumes = (getattr(self, "current_series", None) or {}).get("volume", [])

        if not highs or not lows or not volumes or len(highs) < length:
            return None

        return self._emv(highs, lows, volumes, length)

    def _builtin_ta_iii(self, args: list[Any]) -> float | None:
        """Intraday Intensity Index - measures money flow without volume data.

        Forms:
        - ``ta.iii`` / ``ta.iii()`` — chart high/low/close
        - ``ta.iii(high, low, close)`` — explicit values/series (current bar)
        """
        if len(args) == 0:
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if not highs or not lows or not closes:
                return None
            high = highs[-1]
            low = lows[-1]
            close = closes[-1]
        elif len(args) >= TERNARY:
            high = args[0][-1] if isinstance(args[0], list) and args[0] else args[0]
            low = args[1][-1] if isinstance(args[1], list) and args[1] else args[1]
            close = args[2][-1] if isinstance(args[2], list) and args[2] else args[2]
            high = self._expect_number(high, "high must be numeric")
            low = self._expect_number(low, "low must be numeric")
            close = self._expect_number(close, "close must be numeric")
        else:
            self._error("ta.iii() requires 0 or 3 arguments: high, low, close")
            return None

        if high is None or low is None or close is None:
            return None
        try:
            high_f = float(high)
            low_f = float(low)
            close_f = float(close)
        except (TypeError, ValueError):
            return None

        tr = high_f - low_f
        if tr == 0:
            return 0.0

        iii = 2 * close_f - high_f - low_f
        return iii / tr if tr != 0 else 0.0

    def _builtin_ta_nvi(self, args: list[Any]) -> list[float | None]:
        """Negative Volume Index - cumulative index when volume decreases.

        Forms:
        - ``ta.nvi`` / ``ta.nvi()`` — chart close + volume
        - ``ta.nvi(close, volume)`` — explicit series
        """
        if len(args) == 0:
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
        elif len(args) >= BINARY:
            close_series = self._as_series(args[0])
            volume_series = self._as_series(args[1])
        else:
            self._error("ta.nvi() requires 0 or 2+ arguments: close, volume")
            return []

        if len(close_series) != len(volume_series):
            return [None]

        nvi_values = []
        nvi = 1000.0

        for i in range(len(close_series)):
            if i == 0:
                nvi_values.append(nvi)
                continue

            if close_series[i - 1] != 0:
                close_change = (close_series[i] - close_series[i - 1]) / close_series[i - 1]
            else:
                close_change = 0
            vol = volume_series[i] if isinstance(volume_series[i], (int, float)) else 0

            prev_vol = (
                volume_series[i - 1]
                if i > 0 and isinstance(volume_series[i - 1], (int, float))
                else 0
            )
            if vol < prev_vol:
                nvi = nvi * (1 + close_change)

            nvi_values.append(nvi)

        return nvi_values

    def _builtin_ta_pvi(self, args: list[Any]) -> list[float | None]:
        """Positive Volume Index - cumulative index when volume increases.

        Forms:
        - ``ta.pvi`` / ``ta.pvi()`` — chart close + volume
        - ``ta.pvi(close, volume)`` — explicit series
        """
        if len(args) == 0:
            close_series = self._context_series("close")
            volume_series = self._context_series("volume") or [0.0] * len(close_series)
        elif len(args) >= BINARY:
            close_series = self._as_series(args[0])
            volume_series = self._as_series(args[1])
        else:
            self._error("ta.pvi() requires 0 or 2+ arguments: close, volume")
            return []

        if len(close_series) != len(volume_series):
            return [None]

        pvi_values = []
        pvi = 1000.0

        for i in range(len(close_series)):
            if i == 0:
                pvi_values.append(pvi)
                continue

            if close_series[i - 1] != 0:
                close_change = (close_series[i] - close_series[i - 1]) / close_series[i - 1]
            else:
                close_change = 0
            vol = volume_series[i] if isinstance(volume_series[i], (int, float)) else 0
            prev_vol = (
                volume_series[i - 1]
                if i > 0 and isinstance(volume_series[i - 1], (int, float))
                else 0
            )

            if vol > prev_vol:
                pvi = pvi * (1 + close_change)

            pvi_values.append(pvi)

        return pvi_values

    def _builtin_ta_voi(self, args: list[Any]) -> float:
        """Volume of Imbalance.

        ta.voi(buy_volume, sell_volume)
        Measures imbalance in buy vs sell volume.
        """
        if len(args) < BINARY:
            msg = "ta.voi() requires 2 arguments: buy_volume, sell_volume"
            self._error(msg)

        buy_vol = float(args[0]) if isinstance(args[0], (int, float)) else 0.0
        sell_vol = float(args[1]) if isinstance(args[1], (int, float)) else 0.0

        total = buy_vol + sell_vol
        if total == 0:
            return 0.0

        voi_value = (buy_vol - sell_vol) / total
        return voi_value

    def _builtin_ta_bid_ask_imbalance(self, args: list[Any]) -> dict[str, float]:
        """Bid-Ask Imbalance.

        ta.bid_ask_imbalance(bid_size, ask_size, bid_price, ask_price)
        Measures market microstructure imbalance.
        """
        if len(args) < QUATERNARY:
            msg = "ta.bid_ask_imbalance() requires 4 arguments: bid_size, ask_size, bid_price, ask_price"
            self._error(msg)

        bid_size = float(args[0]) if isinstance(args[0], (int, float)) else 0.0
        ask_size = float(args[1]) if isinstance(args[1], (int, float)) else 0.0
        bid_price = float(args[2]) if isinstance(args[2], (int, float)) else 0.0
        ask_price = float(args[3]) if isinstance(args[3], (int, float)) else 0.0

        total_size = bid_size + ask_size
        if total_size == 0:
            return {"imbalance_ratio": 0.0, "spread": 0.0}

        imbalance = (bid_size - ask_size) / total_size
        spread = ask_price - bid_price if bid_price > 0 else 0.0

        return {"imbalance_ratio": imbalance, "spread": spread}

    def _builtin_ta_volume_weighted_momentum(self, args: list[Any]) -> float | None:
        """Volume Weighted Momentum.

        ta.volume_weighted_momentum(series, volume, length)
        Returns: Momentum value weighted by volume
        """
        if len(args) < TERNARY:
            msg = "ta.volume_weighted_momentum() requires 3 arguments: series, volume, length"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        volume = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series) < length or len(volume) < length:
            return None

        momentum_sum = 0.0
        volume_sum = 0.0

        for i in range(length):
            idx = -1 - i
            if idx - 1 < -len(series):
                break

            price_change = series[idx] - series[idx - 1]
            vol = volume[idx] if isinstance(volume[idx], (int, float)) else 0.0

            momentum_sum += price_change * vol
            volume_sum += vol

        return momentum_sum / volume_sum if volume_sum > 0 else 0.0

    # -- Implementation helpers (private _method prefix) --------------------

    def _obv(self, closes: list[float], volumes: list[float]) -> int:
        """Calculate On-Balance Volume."""
        warmup_length = 3
        if len(closes) != len(volumes) or len(closes) < warmup_length:
            return 0
        obv = 0
        for idx in range(2, len(closes)):
            if closes[idx] > closes[idx - 1]:
                obv += volumes[idx]
            elif closes[idx] < closes[idx - 1]:
                obv -= volumes[idx]
        return obv

    def _mfi(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        period: int,
    ) -> float:
        """Calculate Money Flow Index.

        Aligns H/L/C/V to a common most-recent window (``min(len)`` from the
        end) so mismatched truncated source vs full context volume never
        trip ``zip(strict=True)``. None / non-numeric bars are skipped for
        money-flow direction without raising.
        """
        n = min(len(highs), len(lows), len(closes), len(volumes))
        if n <= period + 2 or period < 1:
            return 50.0
        highs = highs[-n:]
        lows = lows[-n:]
        closes = closes[-n:]
        volumes = volumes[-n:]

        typical_prices: list[float | None] = []
        money_flow: list[float | None] = []
        for high, low, close, volume in zip(highs, lows, closes, volumes, strict=False):
            if (
                not isinstance(high, (int, float))
                or not isinstance(low, (int, float))
                or not isinstance(close, (int, float))
            ):
                typical_prices.append(None)
                money_flow.append(None)
                continue
            vol = float(volume) if isinstance(volume, (int, float)) else 0.0
            tp = (float(high) + float(low) + float(close)) / 3.0
            typical_prices.append(tp)
            money_flow.append(tp * vol)

        positive_flow: list[float] = []
        negative_flow: list[float] = []
        for idx in range(1, len(typical_prices)):
            tp = typical_prices[idx]
            prev = typical_prices[idx - 1]
            mf = money_flow[idx]
            if tp is None or prev is None or mf is None:
                positive_flow.append(0.0)
                negative_flow.append(0.0)
                continue
            if tp > prev:
                positive_flow.append(mf)
                negative_flow.append(0.0)
            else:
                positive_flow.append(0.0)
                negative_flow.append(mf)
        if len(positive_flow) < period:
            return 50.0
        recent_positive = positive_flow[-period:]
        recent_negative = negative_flow[-period:]
        pos_count = sum(1 for value in recent_positive if value > 0)
        neg_count = sum(1 for value in recent_negative if value > 0)
        if pos_count == 0 or neg_count == 0:
            return 50.0
        pos_sum = sum(recent_positive)
        neg_sum = sum(recent_negative)
        if neg_sum == 0:
            return 100.0
        ratio = pos_sum / neg_sum
        return 100 - (100 / (1 + ratio))

    def _accdist(
        self,
        high_series: list[Any],
        low_series: list[Any],
        close_series: list[Any],
        volume_series: list[Any],
    ) -> list[float | None]:
        """Calculate Accumulation/Distribution Index."""
        ad_values = []
        ad = 0.0

        for i in range(len(close_series)):
            high = high_series[i] if i < len(high_series) else 0
            low = low_series[i] if i < len(low_series) else 0
            close = close_series[i] if i < len(close_series) else 0
            vol = volume_series[i] if i < len(volume_series) else 0

            if high == low:
                clv = 0.0
            else:
                clv = ((close - low) - (high - close)) / (high - low)

            ad += clv * vol
            ad_values.append(ad)

        return ad_values

    def _wad(
        self,
        high_series: list[Any],
        low_series: list[Any],
        close_series: list[Any],
        volume_series: list[Any],
    ) -> list[float | None]:
        """Calculate Williams Accumulation/Distribution."""
        wad_values = []
        wad = 0.0

        for i in range(len(close_series)):
            if i == 0:
                wad_values.append(0.0)
                continue

            high = high_series[i] if i < len(high_series) else close_series[i]
            low = low_series[i] if i < len(low_series) else close_series[i]
            close = close_series[i] if i < len(close_series) else 0
            prev_close = close_series[i - 1] if i > 0 and i - 1 < len(close_series) else 0
            vol = volume_series[i] if i < len(volume_series) else 0

            if close > prev_close:
                wad += vol * (close - low)
            elif close < prev_close:
                wad -= vol * (high - close)

            wad_values.append(wad)

        return wad_values

    def _wvad(
        self,
        high_series: list[Any],
        low_series: list[Any],
        close_series: list[Any],
        volume_series: list[Any],
        period: int,
    ) -> list[float | None]:
        """Calculate Williams Volume Accumulation/Distribution."""
        # First get raw WAD
        wad_values = self._wad(high_series, low_series, close_series, volume_series)

        # Get total volume over period
        wvad_values = []
        for i in range(len(wad_values)):
            start_idx = max(0, i - period + 1)
            volume_sum = sum(
                v
                for v in volume_series[start_idx : i + 1]
                if isinstance(v, (int, float))
            )

            if volume_sum > 0:
                wvad = wad_values[i] / volume_sum if wad_values[i] is not None else 0.0
            else:
                wvad = 0.0

            wvad_values.append(wvad)

        return wvad_values

    def _cmf(
        self,
        close_series: list[Any],
        high_series: list[Any],
        low_series: list[Any],
        volume_series: list[Any],
        period: int,
    ) -> list[float | None]:
        """Calculate Chaikin Money Flow."""
        cmf_values = []
        for i in range(len(close_series)):
            start_idx = max(0, i - period + 1)

            clv_sum = 0.0
            vol_sum = 0.0

            for j in range(start_idx, i + 1):
                high_val = high_series[j] if j < len(high_series) else 0
                low_val = low_series[j] if j < len(low_series) else 0
                close_val = close_series[j] if j < len(close_series) else 0
                volume_val = volume_series[j] if j < len(volume_series) else 0

                hl_range = high_val - low_val
                if hl_range != 0:
                    clv = ((close_val - low_val) - (high_val - close_val)) / hl_range
                else:
                    clv = 0.0

                clv_sum += clv * volume_val
                vol_sum += volume_val

            cmf = clv_sum / vol_sum if vol_sum > 0 else 0.0
            cmf_values.append(cmf)

        return cmf_values

    def _klinger(
        self,
        close_series: list[Any],
        volume_series: list[Any],
        fast_period: int,
        slow_period: int,
    ) -> list[float | None]:
        """Calculate Klinger Oscillator."""
        # Calculate true range volume
        trv_values = []
        for i in range(len(close_series)):
            if i == 0:
                trv = 0.0
            else:
                close_val = close_series[i] if i < len(close_series) else 0
                prev_close = close_series[i - 1] if i > 0 else 0
                volume_val = volume_series[i] if i < len(volume_series) else 0

                if close_val > prev_close:
                    trv = volume_val
                elif close_val < prev_close:
                    trv = -volume_val
                else:
                    trv = 0.0

            trv_values.append(trv)

        # Calculate fast and slow EMAs of cumulative TRV
        cumsum_trv = []
        cum = 0.0
        for trv in trv_values:
            cum += trv
            cumsum_trv.append(cum)

        fast_ema = self._ema(cumsum_trv, fast_period)
        slow_ema = self._ema(cumsum_trv, slow_period)

        ko_values: list[float | None] = []
        for i in range(len(fast_ema)):
            if fast_ema[i] is None or slow_ema[i] is None:
                ko_values.append(None)
            else:
                ko_values.append(fast_ema[i] - slow_ema[i])

        return ko_values

    def _apo(self, series: list[Any], fast: int, slow: int) -> list[float | None]:
        """Calculate Absolute Price Oscillator."""
        fast_ema = self._ema(series, fast)
        slow_ema = self._ema(series, slow)

        apo_values: list[float | None] = []
        for i in range(len(series)):
            if fast_ema[i] is None or slow_ema[i] is None:
                apo_values.append(None)
            else:
                apo_values.append(fast_ema[i] - slow_ema[i])

        return apo_values

    def _vpt(self, closes: list[Any], volumes: list[Any]) -> float | None:
        """Calculate Volume Price Trend."""
        if len(closes) < BINARY:
            return None

        # VPT = Previous VPT + Volume * (Price Change / Previous Price)
        prev_close = closes[-2] if len(closes) >= BINARY else closes[-1]
        if prev_close == 0:
            return 0.0

        price_change_pct = (closes[-1] - prev_close) / prev_close
        vpt_val = volumes[-1] * price_change_pct

        return vpt_val

    def _emv(
        self,
        highs: list[Any],
        lows: list[Any],
        volumes: list[Any],
        length: int,
    ) -> float | None:
        """Calculate Ease of Movement."""
        emv_vals: list[float | None] = []
        for i in range(len(highs)):
            if i == 0 or volumes[i] == 0:
                emv_vals.append(None)
                continue

            distance_moved = ((highs[i] + lows[i]) / 2.0) - (
                (highs[i - 1] + lows[i - 1]) / 2.0
            )
            box_height = highs[i] - lows[i]

            if box_height == 0:
                emv_vals.append(None)
            else:
                emv = (
                    (distance_moved / box_height) * (highs[i] - lows[i]) / volumes[i]
                    if volumes[i] != 0
                    else 0
                )
                emv_vals.append(emv)

        valid_emv = [v for v in emv_vals if v is not None]
        if not valid_emv or len(valid_emv) < length:
            return None

        emv_sma = sum(valid_emv[-length:]) / length
        return emv_sma
