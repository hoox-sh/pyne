"""Volume-based Technical Indicators."""

from __future__ import annotations

from typing import Any

from .core import TechnicalHelpers


class VolumeIndicators(TechnicalHelpers):
    """Volume-based technical indicators: OBV, MFI, CMF, WAD, WVAD, EMV, Klinger, APO, VPT."""

    # -- Public API (builtin_ta_ prefix) ------------------------------------

    def _builtin_ta_obv(self, args: list[Any]) -> int:
        """On-Balance Volume indicator.

        ta.obv(close, volume)
        Accumulates volume based on price direction.
        Returns OBV value.
        """
        msg = "ta.obv expects close and volume series"
        if len(args) != 2:  # BINARY
            self._error(msg)
        closes = self._expect_list(args[0], msg)
        volumes = self._expect_list(args[1], msg)
        return self._obv(closes, volumes)

    def _builtin_ta_mfi(self, args: list[Any]) -> float:
        """Money Flow Index indicator.

        ta.mfi(high, low, close, volume, length)
        Combines price and volume for momentum.
        Returns MFI value (0-100).
        """
        msg = "ta.mfi expects high, low, close, volume, length"
        if len(args) != 5:  # QUINARY
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        volumes = self._expect_list(args[3], msg)
        length = self._expect_int(args[4], msg)
        return self._mfi(highs, lows, closes, volumes, length)

    def _builtin_ta_accdist(self, args: list[Any]) -> list[float | None]:
        """Accumulation/Distribution Index - volume-weighted indicator.

        ta.accdist(high, low, close, volume)
        Returns the A/D series.
        """
        min_args = 4
        if len(args) < min_args:
            msg = "ta.accdist() requires 4 arguments: high, low, close, volume"
            self._error(msg)

        high_series = args[0] if isinstance(args[0], list) else [args[0]]
        low_series = args[1] if isinstance(args[1], list) else [args[1]]
        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        volume_series = args[3] if isinstance(args[3], list) else [args[3]]

        return self._accdist(high_series, low_series, close_series, volume_series)

    def _builtin_ta_wad(self, args: list[Any]) -> list[float | None]:
        """Williams Accumulation/Distribution - volume accumulation index.

        ta.wad(high, low, close, volume)
        Returns the WAD series.
        """
        min_args = 4
        if len(args) < min_args:
            msg = "ta.wad() requires 4 arguments: high, low, close, volume"
            self._error(msg)

        high_series = args[0] if isinstance(args[0], list) else [args[0]]
        low_series = args[1] if isinstance(args[1], list) else [args[1]]
        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        volume_series = args[3] if isinstance(args[3], list) else [args[3]]

        return self._wad(high_series, low_series, close_series, volume_series)

    def _builtin_ta_wvad(self, args: list[Any]) -> list[float | None]:
        """Williams Volume Accumulation/Distribution - normalized WAD.

        ta.wvad(high, low, close, volume, period)
        Returns the WVAD series.
        """
        min_args = 4
        if len(args) < min_args:
            msg = "ta.wvad() requires at least 4 arguments: high, low, close, volume"
            self._error(msg)

        high_series = args[0] if isinstance(args[0], list) else [args[0]]
        low_series = args[1] if isinstance(args[1], list) else [args[1]]
        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        volume_series = args[3] if isinstance(args[3], list) else [args[3]]
        period_arg_idx = 4
        default_period = 20
        period = (
            self._expect_int(args[period_arg_idx], "period must be integer")
            if len(args) > period_arg_idx
            else default_period
        )

        return self._wvad(high_series, low_series, close_series, volume_series, period)

    def _builtin_ta_cmf(self, args: list[Any]) -> list[float | None]:
        """Chaikin Money Flow indicator.

        ta.cmf(close, high, low, volume, period)
        Measures money flow into/out of security.
        Returns CMF series.
        """
        if len(args) < 5:
            msg = "ta.cmf() requires 5 arguments: close, high, low, volume, period"
            self._error(msg)

        close_series = args[0] if isinstance(args[0], list) else [args[0]]
        high_series = args[1] if isinstance(args[1], list) else [args[1]]
        low_series = args[2] if isinstance(args[2], list) else [args[2]]
        volume_series = args[3] if isinstance(args[3], list) else [args[3]]
        period = self._expect_int(args[4], "ta.cmf period must be integer")

        return self._cmf(close_series, high_series, low_series, volume_series, period)

    def _builtin_ta_klinger(self, args: list[Any]) -> list[float | None]:
        """Klinger Oscillator.

        ta.klinger(high, low, close, volume, fast_period, slow_period)
        Volume-based momentum oscillator.
        Returns KO series.
        """
        if len(args) < 6:
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
        if len(args) < 3:
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
        if len(args) < 1:
            msg = "ta.vpt() requires 1 argument: series"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        closes = self.current_series.get("close", [])
        volumes = self.current_series.get("volume", [])

        if not closes or not volumes or len(series) < 2:
            return None

        return self._vpt(closes, volumes)

    def _builtin_ta_emv(self, args: list[Any]) -> float | None:
        """Ease of Movement.

        ta.emv(length)
        Measures ease of price movement relative to volume.
        """
        if len(args) < 1:
            msg = "ta.emv() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < 1:
            msg = "EMV length must be >= 1"
            self._error(msg)

        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])
        volumes = self.current_series.get("volume", [])

        if not highs or not lows or not volumes or len(highs) < length:
            return None

        return self._emv(highs, lows, volumes, length)

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
        """Calculate Money Flow Index."""
        if len(closes) <= period + 2:
            return 50.0
        typical_prices = [
            (high + low + close) / 3
            for high, low, close in zip(highs, lows, closes, strict=True)
        ]
        money_flow = [tp * volume for tp, volume in zip(typical_prices, volumes, strict=True)]
        positive_flow: list[float] = []
        negative_flow: list[float] = []
        for idx in range(1, len(typical_prices)):
            if typical_prices[idx] > typical_prices[idx - 1]:
                positive_flow.append(money_flow[idx])
                negative_flow.append(0)
            else:
                positive_flow.append(0)
                negative_flow.append(money_flow[idx])
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

        ko_values = []
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

        apo_values = []
        for i in range(len(series)):
            if fast_ema[i] is None or slow_ema[i] is None:
                apo_values.append(None)
            else:
                apo_values.append(fast_ema[i] - slow_ema[i])

        return apo_values

    def _vpt(self, closes: list[Any], volumes: list[Any]) -> float | None:
        """Calculate Volume Price Trend."""
        if len(closes) < 2:
            return None

        # VPT = Previous VPT + Volume * (Price Change / Previous Price)
        prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
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
        emv_vals = []
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
