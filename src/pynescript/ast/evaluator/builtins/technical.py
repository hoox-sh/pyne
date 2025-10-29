from __future__ import annotations

import math
import statistics

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


UNARY = 1
BINARY = 2
TERNARY = 3
QUATERNARY = 4
QUINARY = 5

MIN_SERIES_LENGTH = 2


class TechnicalAnalysisMixin(BuiltinDispatchMixin):
    """Technical analysis built-ins and supporting utilities."""

    def _technical_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "ta.sma": self._builtin_ta_sma,
            "ta.ema": self._builtin_ta_ema,
            "ta.rsi": self._builtin_ta_rsi,
            "ta.stdev": self._builtin_ta_stdev,
            "ta.change": self._builtin_ta_change,
            "ta.highest": self._builtin_ta_highest,
            "ta.lowest": self._builtin_ta_lowest,
            "ta.wma": self._builtin_ta_wma,
            "ta.bb": self._builtin_ta_bb,
            "ta.macd": self._builtin_ta_macd,
            "ta.atr": self._builtin_ta_atr,
            "ta.stoch": self._builtin_ta_stoch,
            "ta.adx": self._builtin_ta_adx,
            "ta.cci": self._builtin_ta_cci,
            "ta.roc": self._builtin_ta_roc,
            "ta.wpr": self._builtin_ta_wpr,
            "ta.obv": self._builtin_ta_obv,
            "ta.mfi": self._builtin_ta_mfi,
            "ta.crossover": self._builtin_ta_crossover,
            "ta.crossunder": self._builtin_ta_crossunder,
            "ta.cross": self._builtin_ta_cross,
            "ta.falling": self._builtin_ta_falling,
            "ta.highestbars": self._builtin_ta_highestbars,
            "ta.lowestbars": self._builtin_ta_lowestbars,
            "ta.rising": self._builtin_ta_rising,
            "ta.rma": self._builtin_ta_rma,
            "ta.vwap": self._builtin_ta_vwap,
            "ta.vwma": self._builtin_ta_vwma,
            "ta.hma": self._builtin_ta_hma,
            "ta.sar": self._builtin_ta_sar,
            "ta.tsi": self._builtin_ta_tsi,
            "ta.valuewhen": self._builtin_ta_valuewhen,
            "ta.tr": self._builtin_ta_tr,
            "ta.cog": self._builtin_ta_cog,
            "ta.dmi": self._builtin_ta_dmi,
            "ta.kc": self._builtin_ta_kc,
            "ta.kcw": self._builtin_ta_kcw,
            "ta.linreg": self._builtin_ta_linreg,
            "ta.rci": self._builtin_ta_rci,
            "ta.supertrend": self._builtin_ta_supertrend,
            "ta.swma": self._builtin_ta_swma,
            "ta.zigzag": self._builtin_ta_zigzag,
            "ta.range": self._builtin_ta_range,
            "ta.max": self._builtin_ta_max,
            "ta.min": self._builtin_ta_min,
            "ta.mom": self._builtin_ta_mom,
            "ta.cum": self._builtin_ta_cum,
            "ta.dev": self._builtin_ta_dev,
            "ta.median": self._builtin_ta_median,
            "ta.mode": self._builtin_ta_mode,
            "ta.percentrank": self._builtin_ta_percentrank,
            "ta.variance": self._builtin_ta_variance,
            "ta.barssince": self._builtin_ta_barssince,
            "ta.pivothigh": self._builtin_ta_pivothigh,
            "ta.pivotlow": self._builtin_ta_pivotlow,
            "ta.pivot_point_levels": self._builtin_ta_pivot_point_levels,
            # Phase 7 enhancements: Missing indicators
            "ta.iii": self._builtin_ta_iii,
            "ta.nvi": self._builtin_ta_nvi,
            "ta.pvi": self._builtin_ta_pvi,
            "ta.accdist": self._builtin_ta_accdist,
            "ta.wad": self._builtin_ta_wad,
            "ta.wvad": self._builtin_ta_wvad,
            # Phase 8 Tier 1: High-priority indicators
            "ta.kama": self._builtin_ta_kama,
            "ta.dema": self._builtin_ta_dema,
            "ta.tema": self._builtin_ta_tema,
            "ta.cmf": self._builtin_ta_cmf,
            "ta.klinger": self._builtin_ta_klinger,
            "ta.apo": self._builtin_ta_apo,
            "ta.stoch_smooth": self._builtin_ta_stoch_smooth,
            "ta.rsi_divergence": self._builtin_ta_rsi_divergence,
            "ta.macd_signal": self._builtin_ta_macd_signal,
            # Phase 8 Tier 2: Medium-priority indicators
            "ta.ichimoku": self._builtin_ta_ichimoku,
            "ta.donchian": self._builtin_ta_donchian,
            "ta.stochrsi": self._builtin_ta_stochrsi,
            "ta.dpo": self._builtin_ta_dpo,
            "ta.kst": self._builtin_ta_kst,
            "ta.uo": self._builtin_ta_uo,
            "ta.bb_pct": self._builtin_ta_bb_pct,
            "ta.vpt": self._builtin_ta_vpt,
            "ta.beta": self._builtin_ta_beta,
            "ta.r_squared": self._builtin_ta_r_squared,
            "ta.comovement": self._builtin_ta_comovement,
            "ta.atr_stop": self._builtin_ta_atr_stop,
            "ta.fractal": self._builtin_ta_fractal,
            "ta.emv": self._builtin_ta_emv,
            # Phase 8 Tier 3: Specialized indicators
            "ta.engulfing": self._builtin_ta_engulfing,
            "ta.hammer": self._builtin_ta_hammer,
            "ta.gap_detector": self._builtin_ta_gap_detector,
            "ta.voi": self._builtin_ta_voi,
            "ta.bid_ask_imbalance": self._builtin_ta_bid_ask_imbalance,
            "ta.expected_value": self._builtin_ta_expected_value,
            "ta.skewness": self._builtin_ta_skewness,
            "ta.kurtosis": self._builtin_ta_kurtosis,
            "ta.parkinson": self._builtin_ta_parkinson,
            "ta.garman_klass": self._builtin_ta_garman_klass,
            # Phase 8 Tier 4: Enhancement Variants
            "ta.sma_weighted": self._builtin_ta_sma_weighted,
            "ta.ema_cross_signal": self._builtin_ta_ema_cross_signal,
            "ta.rsi_oversold_overbought": self._builtin_ta_rsi_oversold_overbought,
            "ta.atr_normalized": self._builtin_ta_atr_normalized,
            "ta.volume_weighted_momentum": self._builtin_ta_volume_weighted_momentum,
        }

    # -- Public entry points -------------------------------------------------

    def _builtin_ta_sma(self, args: list[Any]) -> list[float | None]:
        series, period = self._expect_series(args, length=2)
        return self._sma(series, period)

    def _builtin_ta_ema(self, args: list[Any]) -> list[float | None]:
        series, period = self._expect_series(args, length=2)
        return self._ema(series, period)

    def _builtin_ta_rsi(self, args: list[Any]) -> float | None:
        series, period = self._expect_series(args, length=2)
        return self._rsi(series, period)

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        series, period = self._expect_series(args, length=2)
        return self._stdev(series, period)

    def _builtin_ta_change(self, args: list[Any]) -> float | None:
        series, period = self._expect_series(args, length=2)
        return self._change(series, period)

    def _builtin_ta_highest(self, args: list[Any]) -> Any:
        series, period = self._expect_series(args, length=2)
        return self._highest(series, period)

    def _builtin_ta_lowest(self, args: list[Any]) -> Any:
        series, period = self._expect_series(args, length=2)
        return self._lowest(series, period)

    def _builtin_ta_wma(self, args: list[Any]) -> float | None:
        series, period = self._expect_series(args, length=2)
        return self._wma(series, period)

    def _builtin_ta_bb(
        self,
        args: list[Any],
    ) -> tuple[float | None, float | None, float | None]:
        msg = "ta.bb expects series, length, and multiplier"
        if len(args) != TERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        length = self._expect_int(args[1], msg)
        multiplier = args[2]
        if not isinstance(multiplier, int | float):
            self._error("ta.bb expects numeric multiplier")
        return self._bollinger_bands(series, length, multiplier)

    def _builtin_ta_macd(self, args: list[Any]) -> tuple[float, float, float]:
        msg = "ta.macd expects series and three lengths"
        if len(args) != QUATERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        fast = self._expect_int(args[1], msg)
        slow = self._expect_int(args[2], msg)
        signal = self._expect_int(args[3], msg)
        return self._macd(series, fast, slow, signal)

    def _builtin_ta_atr(self, args: list[Any]) -> list[float | None]:
        msg = "ta.atr expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._atr(highs, lows, closes, length)

    def _builtin_ta_stoch(self, args: list[Any]) -> tuple[float, float]:
        msg = "ta.stoch expects high, low, close, length, smooth"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        smooth_k = self._expect_int(args[4], msg)
        return self._stoch(highs, lows, closes, length, smooth_k)

    def _builtin_ta_adx(self, args: list[Any]) -> float:
        msg = "ta.adx expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._adx(highs, lows, closes, length)

    def _builtin_ta_cci(self, args: list[Any]) -> float:
        msg = "ta.cci expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._cci(highs, lows, closes, length)

    def _builtin_ta_roc(self, args: list[Any]) -> float:
        series, period = self._expect_series(args, length=2)
        return self._roc(series, period)

    def _builtin_ta_wpr(self, args: list[Any]) -> float:
        msg = "ta.wpr expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._wpr(highs, lows, closes, length)

    def _builtin_ta_obv(self, args: list[Any]) -> int:
        msg = "ta.obv expects close and volume series"
        if len(args) != BINARY:
            self._error(msg)
        closes = self._expect_list(args[0], msg)
        volumes = self._expect_list(args[1], msg)
        return self._obv(closes, volumes)

    def _builtin_ta_mfi(self, args: list[Any]) -> float:
        msg = "ta.mfi expects high, low, close, volume, length"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        volumes = self._expect_list(args[3], msg)
        length = self._expect_int(args[4], msg)
        return self._mfi(highs, lows, closes, volumes, length)

    def _builtin_ta_crossover(self, args: list[Any]) -> bool:
        series1, series2 = self._expect_two_series(args)
        return self._crossover(series1, series2)

    def _builtin_ta_crossunder(self, args: list[Any]) -> bool:
        series1, series2 = self._expect_two_series(args)
        return self._crossunder(series1, series2)

    def _builtin_ta_cross(self, args: list[Any]) -> bool:
        series1, series2 = self._expect_two_series(args)
        return self._cross(series1, series2)

    def _builtin_ta_falling(self, args: list[Any]) -> bool:
        series, period = self._expect_series(args, length=2)
        return self._falling(series, period)

    def _builtin_ta_highestbars(self, args: list[Any]) -> int:
        series, period = self._expect_series(args, length=2)
        return self._highestbars(series, period)

    def _builtin_ta_lowestbars(self, args: list[Any]) -> int:
        series, period = self._expect_series(args, length=2)
        return self._lowestbars(series, period)

    def _builtin_ta_rising(self, args: list[Any]) -> bool:
        series, period = self._expect_series(args, length=2)
        return self._rising(series, period)

    def _builtin_ta_rma(self, args: list[Any]) -> list[float]:
        series, period = self._expect_series(args, length=2)
        return self._rma(series, period)

    def _builtin_ta_vwap(self, args: list[Any]) -> float:
        msg = "ta.vwap expects price-volume values"
        if len(args) != UNARY:
            self._error(msg)
        sequence = self._expect_list(args[0], msg)
        return self._vwap(sequence)

    def _builtin_ta_vwma(self, args: list[Any]) -> list[float | None]:
        series, period = self._expect_series(args, length=2)
        return self._vwma(series, period)

    def _builtin_ta_hma(self, args: list[Any]) -> float | None:
        series, period = self._expect_series(args, length=2)
        return self._hma(series, period)

    def _builtin_ta_sar(self, args: list[Any]) -> list[float]:
        msg = "ta.sar expects high, low, start, increment, max"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        start = self._expect_number(args[2], msg)
        increment = self._expect_number(args[3], msg)
        maximum = self._expect_number(args[4], msg)
        return self._sar(highs, lows, start, increment, maximum)

    def _builtin_ta_tsi(self, args: list[Any]) -> float | None:
        msg = "ta.tsi expects series and two lengths"
        if len(args) != TERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        long_period = self._expect_int(args[1], msg)
        short_period = self._expect_int(args[2], msg)
        return self._tsi(series, long_period, short_period)

    def _builtin_ta_valuewhen(self, args: list[Any]) -> Any:
        msg = "ta.valuewhen expects condition, source, and optional occurrence"
        if len(args) not in {BINARY, TERNARY}:
            self._error(msg)
        condition = self._expect_list(args[0], msg)
        source = self._expect_list(args[1], msg)
        occurrence = self._expect_int(args[2], msg) if len(args) == TERNARY else 0
        return self._valuewhen(condition, source, occurrence)

    def _builtin_ta_tr(self, args: list[Any]) -> list[float]:
        msg = "ta.tr expects high, low, and close"
        if len(args) != TERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        return self._tr(highs, lows, closes)

    # -- Shared validation helpers ------------------------------------------

    def _expect_series(
        self,
        args: list[Any],
        length: int,
    ) -> tuple[list[Any], int]:
        if len(args) != length:
            self._error("Invalid argument count for series-based function")
        series = self._expect_list(args[0], "First argument must be a series")
        period = self._expect_int(
            args[1],
            "Second argument must be an integer length",
        )
        return series, period

    def _expect_two_series(
        self,
        args: list[Any],
    ) -> tuple[list[Any], list[Any]]:
        if len(args) != BINARY:
            self._error("Function takes two series arguments")
        return (
            self._expect_list(args[0], "Function takes two series arguments"),
            self._expect_list(args[1], "Function takes two series arguments"),
        )

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        if not isinstance(value, list):
            self._error(message)
        return value

    def _expect_int(self, value: Any, message: str) -> int:
        if not isinstance(value, int):
            self._error(message)
        return value

    def _expect_number(self, value: Any, message: str) -> float:
        if not isinstance(value, int | float):
            self._error(message)
        return float(value)

    # -- Indicator implementations ------------------------------------------

    def _sma(self, series: list[Any], period: int) -> list[float | None]:
        result: list[float | None] = []
        if not series or period <= 0:
            return result
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = [value for value in series[index - period + 1 : index + 1] if value is not None]
            if not window:
                result.append(None)
                continue
            result.append(sum(window) / len(window))
        return result

    def _ema(self, series: list[Any], period: int) -> list[float | None]:
        if not series or period <= 0:
            return [None] * len(series)
        alpha = 2 / (period + 1)
        ema_values: list[float | None] = []
        first_valid = next(
            (i for i, value in enumerate(series) if value is not None),
            -1,
        )
        if first_valid == -1:
            return [None] * len(series)
        ema_values.extend([None] * first_valid)
        ema_values.append(series[first_valid])
        for idx in range(first_valid + 1, len(series)):
            value = series[idx]
            if value is None:
                ema_values.append(ema_values[-1])
                continue
            previous = ema_values[-1]
            if previous is None:
                self._error("EMA requires a previous value")
            ema_values.append(alpha * value + (1 - alpha) * previous)
        return ema_values

    def _min_series(
        self,
        series: list[Any],
        period: int,
    ) -> list[float | None]:
        result: list[float | None] = []
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            valid = [value for value in window if value is not None]
            result.append(min(valid) if valid else None)
        return result

    def _max_series(
        self,
        series: list[Any],
        period: int,
    ) -> list[float | None]:
        result: list[float | None] = []
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            valid = [value for value in window if value is not None]
            result.append(max(valid) if valid else None)
        return result

    def _stoch(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
        smooth_k: int,
    ) -> tuple[float, float]:
        low_n = self._min_series(lows, period)
        high_n = self._max_series(highs, period)
        raw_values: list[float | None] = []
        for idx, close in enumerate(closes):
            high_value = high_n[idx]
            low_value = low_n[idx]
            if high_value is not None and low_value is not None and high_value != low_value:
                raw_values.append(100 * (close - low_value) / (high_value - low_value))
            else:
                raw_values.append(None)
        valid_values = [value for value in raw_values if value is not None]
        if not valid_values:
            return 0.0, 0.0
        last_k = valid_values[-1]
        if len(valid_values) <= smooth_k + 1:
            return last_k, 0.0
        smoothed_k = self._ema(valid_values, smooth_k)
        if not smoothed_k:
            return last_k, 0.0
        last_d = smoothed_k[-1]
        if last_d is None:
            last_d = 0.0
        return last_k, last_d

    def _adx(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        if period <= 0:
            return 0.0
        if min(len(highs), len(lows), len(closes)) < period:
            return 0.0
        true_ranges = self._tr(highs, lows, closes)
        plus_dm = [math.nan]
        minus_dm = [math.nan]
        for idx in range(1, len(highs)):
            high_diff = highs[idx] - highs[idx - 1]
            low_diff = lows[idx - 1] - lows[idx]
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)
        atr = self._rma(true_ranges, period)
        if not atr or all(value in {None, math.nan, 0} for value in atr):
            return 0.0
        plus_di = [100 * dm / tr if tr else 0 for dm, tr in zip(self._rma(plus_dm, period), atr, strict=True)]
        minus_di = [100 * dm / tr if tr else 0 for dm, tr in zip(self._rma(minus_dm, period), atr, strict=True)]
        dx = [100 * abs(p - m) / (p + m) if (p + m) else 0 for p, m in zip(plus_di, minus_di, strict=True)]
        adx_series = self._rma(dx, period)
        return next(
            (value for value in reversed(adx_series) if value not in {None, math.nan}),
            0.0,
        )

    def _cci(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        if period <= 0 or len(closes) < period:
            return 0.0
        typical_prices = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes, strict=True)]
        sma_values = self._sma(typical_prices, period)
        mean_devs: list[float | None] = []
        for idx in range(len(typical_prices)):
            if idx < period - 1:
                mean_devs.append(None)
                continue
            window = typical_prices[idx - period + 1 : idx + 1]
            sma_value = sma_values[idx]
            if sma_value is None:
                mean_devs.append(None)
                continue
            mean_devs.append(statistics.mean(abs(value - sma_value) for value in window))
        last_mean_dev = next(
            (value for value in reversed(mean_devs) if value not in {None, 0}),
            None,
        )
        if last_mean_dev is None:
            return 0.0
        last_tp = next(
            (value for value in reversed(typical_prices) if value is not None),
            0,
        )
        last_sma = next(
            (value for value in reversed(sma_values) if value is not None),
            0,
        )
        return (last_tp - last_sma) / (0.015 * last_mean_dev)

    def _roc(self, series: list[float], period: int) -> float:
        if period <= 0 or len(series) <= period:
            return 0.0
        previous_index = len(series) - period - 1
        if previous_index < 0:
            return 0.0
        baseline = series[previous_index]
        if baseline in {None, 0}:
            return 0.0
        earlier_index = previous_index - 1
        denominator = baseline
        if earlier_index >= 0:
            earlier = series[earlier_index]
            if earlier not in {None, 0}:
                denominator = earlier
        change = series[-1] - baseline
        return 100 * change / denominator

    def _wpr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        if len(closes) < period or period <= 0:
            return 0.0
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        if highest_high == lowest_low:
            return 0.0
        return -100 * (highest_high - closes[-1]) / (highest_high - lowest_low)

    def _obv(self, closes: list[float], volumes: list[float]) -> int:
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
        if len(closes) <= period + 2:
            return 50.0
        typical_prices = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes, strict=True)]
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

    def _atr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> list[float | None]:
        if period <= 0:
            return []
        tr_values: list[float] = []
        for idx in range(1, len(closes)):
            high = highs[idx]
            low = lows[idx]
            prev_close = closes[idx - 1]
            tr_values.append(
                max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
            )
        if not tr_values:
            return []
        if len(tr_values) < period:
            average = statistics.mean(tr_values)
            return [average]
        return self._ema(tr_values, period)

    def _tr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> list[float]:
        result = [math.nan]
        for idx in range(1, len(closes)):
            result.append(
                max(
                    highs[idx] - lows[idx],
                    abs(highs[idx] - closes[idx - 1]),
                    abs(lows[idx] - closes[idx - 1]),
                )
            )
        return result

    def _format_series(self, series: list[Any]) -> list[float]:
        return [float(value) if value is not None else math.nan for value in series]

    def _rma(self, series: list[Any], period: int) -> list[float]:
        formatted = self._format_series(series)
        if not formatted or period <= 0:
            return [math.nan] * len(formatted)
        alpha = 1.0 / period
        rma_values: list[float] = []
        first_valid = next(
            (idx for idx, value in enumerate(formatted) if not math.isnan(value)),
            -1,
        )
        if first_valid == -1:
            return [math.nan] * len(formatted)
        rma_values.extend([math.nan] * first_valid)
        initial_window = [value for value in formatted[first_valid : first_valid + period] if not math.isnan(value)]
        if not initial_window:
            return [math.nan] * len(formatted)
        current = sum(initial_window) / len(initial_window)
        rma_values.extend([math.nan] * (period - 1))
        rma_values.append(current)
        for idx in range(first_valid + period, len(formatted)):
            value = formatted[idx]
            if math.isnan(value):
                rma_values.append(current)
                continue
            current = alpha * value + (1 - alpha) * current
            rma_values.append(current)
        while len(rma_values) < len(formatted):
            rma_values.append(rma_values[-1])
        return rma_values[: len(formatted)]

    def _mom(self, series: list[float], period: int) -> float:
        if len(series) <= period:
            return 0.0
        return series[-1] - series[-period - 1]

    def _sar(
        self,
        highs: list[float],
        lows: list[float],
        start: float,
        increment: float,
        maximum: float,
    ) -> list[float]:
        values, _ = self._sar_full(highs, lows, start, increment, maximum)
        return values

    def _sar_full(
        self,
        highs: list[float],
        lows: list[float],
        start: float,
        increment: float,
        maximum: float,
    ) -> tuple[list[float], int]:
        if not highs or not lows:
            return [], 0
        sar_values = [lows[0]]
        trend = 1
        af = start
        ep = highs[0]
        for idx in range(1, len(highs)):
            previous = sar_values[-1]
            if trend == 1:
                sar = previous + af * (ep - previous)
                if highs[idx] > ep:
                    ep = highs[idx]
                    af = min(af + increment, maximum)
                if sar > lows[idx]:
                    trend = -1
                    sar = ep
                    ep = lows[idx]
                    af = start
            else:
                sar = previous - af * (previous - ep)
                if lows[idx] < ep:
                    ep = lows[idx]
                    af = min(af + increment, maximum)
                if sar < highs[idx]:
                    trend = 1
                    sar = ep
                    ep = highs[idx]
                    af = start
            sar_values.append(sar)
        return sar_values, trend

    def _crossover(self, series1: list[float], series2: list[float]) -> bool:
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        return series1[-2] < series2[-2] and series1[-1] > series2[-1]

    def _crossunder(self, series1: list[float], series2: list[float]) -> bool:
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        return series1[-2] > series2[-2] and series1[-1] < series2[-1]

    def _cross(self, series1: list[float], series2: list[float]) -> bool:
        return bool(self._crossover(series1, series2) or self._crossunder(series1, series2))

    def _falling(self, series: list[float], period: int) -> bool:
        if len(series) < period:
            return False
        for idx in range(1, period):
            if series[-idx] <= series[-idx - 1]:
                return False
        return True

    def _rising(self, series: list[float], period: int) -> bool:
        if len(series) < period:
            return False
        for idx in range(1, period):
            if series[-idx] >= series[-idx - 1]:
                return False
        return True

    def _highest(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        return max(series[-period:])

    def _lowest(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        return min(series[-period:])

    def _highestbars(self, series: list[float], period: int) -> int:
        if len(series) < period:
            return -1
        window = series[-period:]
        value = max(window)
        return -window[::-1].index(value)

    def _lowestbars(self, series: list[float], period: int) -> int:
        if len(series) < period:
            return -1
        window = series[-period:]
        value = min(window)
        return -window[::-1].index(value)

    def _rsi(self, series: list[float], period: int) -> float | None:
        if len(series) < period + 1:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for idx in range(1, len(series)):
            change = series[idx] - series[idx - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        avg_gain = self._rma(gains, period)[-1]
        avg_loss = self._rma(losses, period)[-1]
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _stdev(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        return statistics.stdev(series[-period:])

    def _vwap(self, hlc3_volume: list[float]) -> float:
        if not hlc3_volume:
            return 0
        return sum(hlc3_volume) / len(hlc3_volume)

    def _vwma(self, series: list[float], period: int) -> list[float]:
        return self._sma(series, period)

    def _wma(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        weights = list(range(1, period + 1))
        total = sum(weights)
        return sum(series[-idx] * (period - idx + 1) for idx in range(1, period + 1)) / total

    def _hma(self, series: list[float], period: int) -> float | None:
        half_period = period // 2
        sqrt_period = int(math.sqrt(period))
        wma_half = self._wma(series, half_period)
        wma_full = self._wma(series, period)
        if wma_half is None or wma_full is None:
            return None
        diff = [2 * wma_half[i] - wma_full[i] for i in range(min(len(wma_half), len(wma_full)))]
        return self._wma(diff, sqrt_period)

    def _tsi(
        self,
        series: list[float],
        long_period: int,
        short_period: int,
    ) -> float | None:
        if len(series) < long_period + short_period:
            return None
        momentum = [series[idx] - series[idx - 1] for idx in range(1, len(series))]
        abs_momentum = [abs(value) for value in momentum]
        ema_mom = self._ema(momentum, long_period)
        ema_ema_mom = self._ema(ema_mom, short_period)
        ema_abs = self._ema(abs_momentum, long_period)
        ema_ema_abs = self._ema(ema_abs, short_period)
        if ema_ema_abs[-1] == 0:
            return 0
        return 100 * (ema_ema_mom[-1] / ema_ema_abs[-1])

    def _valuewhen(
        self,
        condition: list[bool],
        source: list[Any],
        occurrence: int,
    ) -> Any:
        indices = [index for index, flag in enumerate(condition) if flag]
        if not indices or occurrence >= len(indices):
            return None
        return source[indices[-(occurrence + 1)]]

    def _change(self, source: list[float], length: int = 1) -> float | None:
        if len(source) <= length:
            return None
        return source[-1] - source[-1 - length]

    def _bollinger_bands(
        self,
        series: list[float],
        period: int,
        multiplier: float,
    ) -> tuple[float | None, float | None, float | None]:
        sma_values = self._sma(series, period)
        middle = sma_values[-1] if sma_values else None
        deviation = self._stdev(series, period)
        if middle is None or deviation is None:
            return None, None, None
        upper = middle + deviation * multiplier
        lower = middle - deviation * multiplier
        return upper, middle, lower

    def _macd(
        self,
        series: list[float],
        fast: int,
        slow: int,
        signal: int,
    ) -> tuple[float, float, float]:
        ema_fast = self._ema(series, fast)
        ema_slow = self._ema(series, slow)
        macd_line = [
            fast_val - slow_val if fast_val is not None and slow_val is not None else None
            for fast_val, slow_val in zip(ema_fast, ema_slow, strict=True)
        ]
        signal_line = self._ema(macd_line, signal)
        histogram = [
            macd_val - sig_val if macd_val is not None and sig_val is not None else None
            for macd_val, sig_val in zip(macd_line, signal_line, strict=True)
        ]
        last_macd = next(
            (value for value in reversed(macd_line) if value is not None),
            0.0,
        )
        last_signal = next(
            (value for value in reversed(signal_line) if value is not None),
            0.0,
        )
        last_hist = next(
            (value for value in reversed(histogram) if value is not None),
            0.0,
        )
        return last_macd, last_signal, last_hist

    def _builtin_ta_cog(self, args: list[Any]) -> float:
        """Center of Gravity oscillator."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 1:
            self._error("ta.cog length must be positive")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        num_sum = sum((i + 1) * val for i, val in enumerate(reversed(window)) if val is not None)
        den_sum = sum(val for val in window if val is not None)

        if den_sum == 0:
            return math.nan
        return -num_sum / den_sum

    def _builtin_ta_dmi(self, args: list[Any]) -> tuple[float, float]:
        """Directional Movement Index (returns +DI, -DI)."""
        if len(args) != QUATERNARY:
            self._error("ta.dmi takes high, low, close series and length")

        highs = self._expect_list(args[0], "ta.dmi takes high, low, close series and length")
        lows = self._expect_list(args[1], "ta.dmi takes high, low, close series and length")
        closes = self._expect_list(args[2], "ta.dmi takes high, low, close series and length")
        length = self._expect_int(args[3], "ta.dmi takes high, low, close series and length")

        if length < 1:
            self._error("ta.dmi length must be positive")
        if not (len(highs) == len(lows) == len(closes)):
            self._error("ta.dmi series must have equal length")

        plus_dm = []
        minus_dm = []

        for i in range(len(highs)):
            if i == 0:
                plus_dm.append(0.0)
                minus_dm.append(0.0)
            else:
                high_diff = (highs[i] if highs[i] is not None else 0) - (
                    highs[i - 1] if highs[i - 1] is not None else 0
                )
                low_diff = (lows[i - 1] if lows[i - 1] is not None else 0) - (lows[i] if lows[i] is not None else 0)
                plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
                minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)

        atr_series = self._builtin_ta_atr([highs, lows, closes, length])
        atr_val = atr_series[-1] if atr_series else 1

        plus_di = 100 * (sum(plus_dm[-length:]) / length) / atr_val if atr_val else 0
        minus_di = 100 * (sum(minus_dm[-length:]) / length) / atr_val if atr_val else 0

        return plus_di, minus_di

    def _builtin_ta_kc(self, args: list[Any]) -> tuple[float, float, float]:
        """Keltner Channels (returns middle, upper, lower)."""
        if len(args) not in {TERNARY, QUATERNARY}:
            self._error("ta.kc takes high, low, close series, length, and optional offset_percent")

        highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
        lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
        closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        length = self._expect_int(args[3], "ta.kc length must be integer") if len(args) > 3 else 0
        offset_percent = 1.0 if len(args) < 5 else (args[4] if isinstance(args[4], (int, float)) else 1.0)

        if length < 1:
            self._error("ta.kc length must be positive")

        # Middle line = EMA of closes
        ema_vals = self._ema(closes, length)
        middle = ema_vals[-1] if ema_vals else math.nan

        # ATR for channel width
        atr_series = self._builtin_ta_atr([highs, lows, closes, length])
        atr_val = atr_series[-1] if atr_series else 0

        channel_width = atr_val * offset_percent
        upper = middle + channel_width if middle is not None else math.nan
        lower = middle - channel_width if middle is not None else math.nan

        return middle, upper, lower

    def _builtin_ta_kcw(self, args: list[Any]) -> float:
        """Keltner Channels Width."""
        if len(args) not in {TERNARY, QUATERNARY}:
            self._error("ta.kcw takes high, low, close series, length, and optional offset_percent")

        _, upper, lower = self._builtin_ta_kc(args)
        if math.isnan(upper) or math.isnan(lower):
            return math.nan
        return upper - lower

    def _builtin_ta_linreg(self, args: list[Any]) -> float:
        """Linear Regression value."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 2:
            self._error("ta.linreg length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [v for v in window if v is not None]

        if len(valid_values) < 2:
            return math.nan

        x = list(range(len(valid_values)))
        mean_x = sum(x) / len(x)
        mean_y = sum(valid_values) / len(valid_values)

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, valid_values, strict=True))
        denominator = sum((xi - mean_x) ** 2 for xi in x)

        if denominator == 0:
            return mean_y

        slope = numerator / denominator
        return slope * (len(valid_values) - 1) + mean_y

    def _builtin_ta_rci(self, args: list[Any]) -> float:
        """Rank Correlation Index (Spearman's correlation)."""
        if len(args) != BINARY:
            self._error("ta.rci takes source series and length")

        series = self._expect_list(args[0], "ta.rci takes source series and length")
        length = self._expect_int(args[1], "ta.rci takes source series and length")

        if length < 2:
            self._error("ta.rci length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [(i, v) for i, v in enumerate(window) if v is not None]

        if len(valid_values) < 2:
            return math.nan

        ranks_idx = sorted(range(len(valid_values)), key=lambda i: i)
        ranks_val = sorted(range(len(valid_values)), key=lambda i: valid_values[i][1])

        rank_dict_idx = {idx: rank for rank, idx in enumerate(ranks_idx)}
        rank_dict_val = {idx: rank for rank, idx in enumerate(ranks_val)}

        d_squared = sum((rank_dict_idx[i] - rank_dict_val[i]) ** 2 for i in range(len(valid_values)))
        n = len(valid_values)
        return 1 - (6 * d_squared) / (n * (n * n - 1)) if n > 1 else math.nan

    def _builtin_ta_supertrend(self, args: list[Any]) -> tuple[float, float, int]:
        """Supertrend indicator (returns final_lowerband, final_upperband, direction)."""
        if len(args) != TERNARY:
            self._error("ta.supertrend takes high, low series and length, multiplier")

        highs = self._expect_list(args[0], "ta.supertrend takes high, low, length, multiplier")
        lows = self._expect_list(args[1], "ta.supertrend takes high, low, length, multiplier")
        length = self._expect_int(args[2], "ta.supertrend takes high, low, length, multiplier")
        multiplier = args[3] if len(args) > 3 else 1.0

        if length < 1:
            self._error("ta.supertrend length must be positive")

        atr_series = self._builtin_ta_atr([highs, lows, [0] * len(highs), length])
        highest_high = max((h for h in highs[-length:] if h is not None), default=0)
        lowest_low = min((ll for ll in lows[-length:] if ll is not None), default=0)

        basic_ub = (highest_high + lowest_low) / 2 + multiplier * (atr_series[-1] if atr_series else 0)
        basic_lb = (highest_high + lowest_low) / 2 - multiplier * (atr_series[-1] if atr_series else 0)

        direction = 1 if highs[-1] > basic_ub else -1 if lows[-1] < basic_lb else 1

        return basic_lb, basic_ub, direction

    def _builtin_ta_swma(self, args: list[Any]) -> float:
        """Symmetric Weighted Moving Average."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 1:
            self._error("ta.swma length must be positive")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [v for v in window if v is not None]

        if not valid_values:
            return math.nan

        # Symmetric weights: [1, 2, 3, ..., n, ..., 3, 2, 1]
        n = len(valid_values)
        if n == 1:
            return valid_values[0]

        weights = []
        for i in range(n):
            if i < n // 2:
                weights.append(i + 1)
            elif i > (n - 1) // 2:
                weights.append(n - i)
            else:
                weights.append(n // 2 + 1)

        weighted_sum = sum(v * w for v, w in zip(valid_values, weights, strict=True))
        return weighted_sum / sum(weights)

    def _builtin_ta_zigzag(self, args: list[Any]) -> tuple[float, float, int]:
        """Zigzag pattern detector (returns high, low, direction)."""
        if len(args) != BINARY:
            self._error("ta.zigzag takes source series and percent threshold")

        series = self._expect_list(args[0], "ta.zigzag takes source series and percent threshold")
        threshold = args[1] if isinstance(args[1], (int, float)) else 5.0

        if len(series) < 2:
            return math.nan, math.nan, 0

        # Find peaks and troughs
        highs = [v for v in series if v is not None]
        if len(highs) < 2:
            return math.nan, math.nan, 0

        recent_high = max(highs[-2:])
        recent_low = min(highs[-2:])

        percent_change = (recent_high - recent_low) / recent_low * 100 if recent_low else 0

        direction = 1 if recent_high == highs[-1] else -1

        return recent_high, recent_low, 1 if percent_change > threshold else direction

    def _builtin_ta_range(self, args: list[Any]) -> float | None:
        """Range = highest - lowest over a period."""
        series, period = self._expect_series(args, length=2)
        return self._range(series, period)

    def _builtin_ta_max(self, args: list[Any]) -> float | None:
        """Maximum value over a period (alias for ta.highest)."""
        series, period = self._expect_series(args, length=2)
        return self._highest(series, period)

    def _builtin_ta_min(self, args: list[Any]) -> float | None:
        """Minimum value over a period (alias for ta.lowest)."""
        series, period = self._expect_series(args, length=2)
        return self._lowest(series, period)

    def _builtin_ta_mom(self, args: list[Any]) -> float | None:
        """Momentum = current value - previous value at specified length."""
        series, period = self._expect_series(args, length=2)
        return self._momentum(series, period)

    def _builtin_ta_cum(self, args: list[Any]) -> float:
        """Cumulative sum of values in series."""
        msg = "ta.cum expects a series"
        if len(args) != UNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        return self._cumsum(series)

    def _builtin_ta_dev(self, args: list[Any]) -> float | None:
        """Deviation from mean (standard deviation)."""
        series, period = self._expect_series(args, length=2)
        return self._dev(series, period)

    def _builtin_ta_median(self, args: list[Any]) -> float | None:
        """Median value over a period."""
        series, period = self._expect_series(args, length=2)
        return self._median(series, period)

    def _builtin_ta_mode(self, args: list[Any]) -> float | None:
        """Mode (most frequent value) over a period."""
        series, period = self._expect_series(args, length=2)
        return self._mode(series, period)

    def _builtin_ta_percentrank(self, args: list[Any]) -> float | None:
        """Percentile rank of current value in period."""
        series, period = self._expect_series(args, length=2)
        return self._percentrank(series, period)

    def _builtin_ta_variance(self, args: list[Any]) -> float | None:
        """Variance over a period."""
        series, period = self._expect_series(args, length=2)
        return self._variance(series, period)

    def _range(self, series: list[float], period: int) -> float | None:
        """Range = highest - lowest over a period."""
        highest = self._highest(series, period)
        lowest = self._lowest(series, period)
        if highest is None or lowest is None:
            return None
        return highest - lowest

    def _momentum(self, series: list[float], period: int) -> float | None:
        """Momentum = current value - previous value at specified period."""
        if len(series) <= period:
            return None
        return series[-1] - series[-1 - period] if series[-1] is not None and series[-1 - period] is not None else None

    def _cumsum(self, series: list[Any]) -> float:
        """Cumulative sum of all values in series."""
        total = 0.0
        for value in series:
            if value is not None and isinstance(value, (int, float)):
                total += value
        return total

    def _dev(self, series: list[float], period: int) -> float | None:
        """Deviation = average absolute deviation from mean."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if not valid_values:
            return None
        mean = sum(valid_values) / len(valid_values)
        dev = sum(abs(v - mean) for v in valid_values) / len(valid_values)
        return dev

    def _median(self, series: list[float], period: int) -> float | None:
        """Median value over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = sorted([v for v in window if v is not None])
        if not valid_values:
            return None
        return statistics.median(valid_values)

    def _mode(self, series: list[float], period: int) -> float | None:
        """Mode (most frequent value) over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if not valid_values:
            return None
        try:
            return statistics.mode(valid_values)
        except statistics.StatisticsError:
            # No unique mode, return the first value
            return valid_values[0] if valid_values else None

    def _percentrank(self, series: list[float], period: int) -> float | None:
        """Percentile rank of current value in period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = sorted([v for v in window if v is not None])
        if not valid_values or len(valid_values) < 2:
            return 50.0
        current = series[-1]
        if current is None:
            return None
        count_below = sum(1 for v in valid_values if v < current)
        return (count_below / len(valid_values)) * 100

    def _variance(self, series: list[float], period: int) -> float | None:
        """Variance over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if len(valid_values) < 2:
            return None
        return statistics.variance(valid_values)

    def _builtin_ta_barssince(self, args: list[Any]) -> int | None:
        """Bars since condition was last true."""
        if len(args) != 1:
            msg = "ta.barssince() takes exactly one argument"
            self._error(msg)
        condition = args[0]
        # If condition is a list (series), check from the end backwards
        if isinstance(condition, list):
            for i in range(len(condition) - 1, -1, -1):
                is_true = condition[i] is True or (condition[i] is not None and condition[i] is not False)
                if is_true:
                    return len(condition) - 1 - i
            return len(condition) - 1
        # If condition is boolean, return 0 if true, 1 if false
        is_true = condition is True or (condition is not None and condition is not False)
        if is_true:
            return 0
        return 1

    def _builtin_ta_pivothigh(self, args: list[Any]) -> float | None:
        """Find the highest point (pivot high) in a window.

        ta.pivothigh(source, leftbars, rightbars)
        Finds a pivot high - a point where left_bars bars to the left are lower
        and right_bars bars to the right are lower.
        """
        if len(args) < 3:
            msg = "ta.pivothigh() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = args[0]
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        # If source is a list (series), check if current value is a pivot high
        if isinstance(source, list):
            if len(source) <= left_bars + right_bars:
                return None

            # Get current value (last in series)
            current_idx = len(source) - 1
            current = source[current_idx]

            if current is None:
                return None

            # Check left bars
            for i in range(1, left_bars + 1):
                if current_idx - i < 0:
                    return None
                left_val = source[current_idx - i]
                if left_val is not None and left_val >= current:
                    return None

            # Check right bars - would need future bars
            # For now, only check left bars
            return float(current)

        return float(source) if source is not None else None

    def _builtin_ta_pivotlow(self, args: list[Any]) -> float | None:
        """Find the lowest point (pivot low) in a window.

        ta.pivotlow(source, leftbars, rightbars)
        Finds a pivot low - a point where left_bars bars to the left are higher
        and right_bars bars to the right are higher.
        """
        if len(args) < 3:
            msg = "ta.pivotlow() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = args[0]
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        # If source is a list (series), check if current value is a pivot low
        if isinstance(source, list):
            if len(source) <= left_bars + right_bars:
                return None

            # Get current value (last in series)
            current_idx = len(source) - 1
            current = source[current_idx]

            if current is None:
                return None

            # Check left bars
            for i in range(1, left_bars + 1):
                if current_idx - i < 0:
                    return None
                left_val = source[current_idx - i]
                if left_val is not None and left_val <= current:
                    return None

            # Check right bars - would need future bars
            # For now, only check left bars
            return float(current)

        return float(source) if source is not None else None

    def _builtin_ta_pivot_point_levels(self, args: list[Any]) -> dict[str, float] | None:
        """Calculate pivot point levels.

        ta.pivot_point_levels(high, low, close, is_traditional)
        Returns a dictionary with pivot point levels.
        """
        if len(args) < 3:
            msg = "ta.pivot_point_levels() requires at least 3 arguments: high, low, close"
            self._error(msg)

        high = self._expect_number(args[0], "high must be numeric")
        low = self._expect_number(args[1], "low must be numeric")
        close = self._expect_number(args[2], "close must be numeric")
        is_traditional = args[3] if len(args) > 3 else True

        if high is None or low is None or close is None:
            return None

        # Calculate pivot point levels (traditional pivot points)
        pivot = (high + low + close) / 3.0

        if is_traditional:
            # Traditional pivot points
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        else:
            # Fibonacci pivot points
            diff = high - low
            r1 = pivot + 0.382 * diff
            s1 = pivot - 0.382 * diff
            r2 = pivot + 0.618 * diff
            s2 = pivot - 0.618 * diff
            r3 = pivot + diff
            s3 = pivot - diff

        return {
            "pivot": pivot,
            "r1": r1,
            "s1": s1,
            "r2": r2,
            "s2": s2,
            "r3": r3,
            "s3": s3,
        }

    # Phase 7: Missing Indicators
    def _builtin_ta_iii(self, args: list[Any]) -> float | None:
        """Intraday Intensity Index - measures money flow without volume data.

        ta.iii(high, low, close)
        Returns the intraday intensity index value.
        """
        min_args = 3
        if len(args) < min_args:
            msg = "ta.iii() requires 3 arguments: high, low, close"
            self._error(msg)

        high = self._expect_number(args[0], "high must be numeric")
        low = self._expect_number(args[1], "low must be numeric")
        close = self._expect_number(args[2], "close must be numeric")

        if high is None or low is None or close is None:
            return None

        # Calculate true range
        tr = high - low
        if tr == 0:
            return 0.0

        # Calculate IIIprice line
        iii = 2 * close - high - low
        return iii / tr if tr != 0 else 0.0

    def _builtin_ta_nvi(self, args: list[Any]) -> list[float | None]:
        """Negative Volume Index - cumulative index when volume decreases.

        ta.nvi(close, volume, period)
        Returns the NVI series.
        """
        min_args = 2
        if len(args) < min_args:
            msg = "ta.nvi() requires at least 2 arguments: close, volume"
            self._error(msg)

        close_series = args[0] if isinstance(args[0], list) else [args[0]]
        volume_series = args[1] if isinstance(args[1], list) else [args[1]]

        if len(close_series) != len(volume_series):
            return [None]

        nvi_values = []
        nvi = 1000.0

        for i in range(len(close_series)):
            if i == 0:
                nvi_values.append(nvi)
                continue

            if close_series[i - 1] != 0:
                close_change = (close_series[i] - close_series[i - 1]) / close_series[
                    i - 1
                ]
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

        ta.pvi(close, volume, period)
        Returns the PVI series.
        """
        min_args = 2
        if len(args) < min_args:
            msg = "ta.pvi() requires at least 2 arguments: close, volume"
            self._error(msg)

        close_series = args[0] if isinstance(args[0], list) else [args[0]]
        volume_series = args[1] if isinstance(args[1], list) else [args[1]]

        if len(close_series) != len(volume_series):
            return [None]

        pvi_values = []
        pvi = 1000.0

        for i in range(len(close_series)):
            if i == 0:
                pvi_values.append(pvi)
                continue

            if close_series[i - 1] != 0:
                close_change = (close_series[i] - close_series[i - 1]) / close_series[
                    i - 1
                ]
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

        wad_values = []
        wad = 0.0

        for i in range(len(close_series)):
            if i == 0:
                wad_values.append(0.0)
                continue

            high = high_series[i] if i < len(high_series) else close_series[i]
            low = low_series[i] if i < len(low_series) else close_series[i]
            close = close_series[i] if i < len(close_series) else 0
            prev_close = (
                close_series[i - 1] if i > 0 and i - 1 < len(close_series) else 0
            )
            vol = volume_series[i] if i < len(volume_series) else 0

            if close > prev_close:
                wad += vol * (close - low)
            elif close < prev_close:
                wad -= vol * (high - close)

            wad_values.append(wad)

        return wad_values

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

        # First get raw WAD
        wad_values = self._builtin_ta_wad([high_series, low_series, close_series, volume_series])

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
                wvad = (
                    wad_values[i] / volume_sum if wad_values[i] is not None else 0.0
                )
            else:
                wvad = 0.0

            wvad_values.append(wvad)

        return wvad_values

    # -- Phase 8 Tier 1: High-Priority Indicators ---------------------------

    def _builtin_ta_kama(self, args: list[Any]) -> list[float | None]:
        """Kaufman's Adaptive Moving Average.

        ta.kama(series, length, fast_period, slow_period)
        Adapts based on market efficiency ratio (smoothing constant).
        Returns KAMA series.
        """
        if len(args) < 4:
            msg = "ta.kama() requires 4 arguments: series, length, fast_period, slow_period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.kama length must be integer")
        fast = self._expect_int(args[2], "ta.kama fast_period must be integer")
        slow = self._expect_int(args[3], "ta.kama slow_period must be integer")

        if length < 1:
            return [None] * len(series)

        kama_values = [None] * length
        kama = series[length - 1] if length <= len(series) else 0.0

        for i in range(length, len(series)):
            change = abs(series[i] - series[i - length])
            volatility = sum(abs(series[i - j] - series[i - j - 1]) for j in range(length))

            if volatility != 0:
                efficiency = change / volatility
                fastest = 2.0 / (fast + 1.0)
                slowest = 2.0 / (slow + 1.0)
                smoothing = efficiency * (fastest - slowest) + slowest
                sc = smoothing * smoothing
            else:
                sc = (2.0 / (slow + 1.0)) ** 2

            kama = kama + sc * (series[i] - kama)
            kama_values.append(kama)

        return kama_values

    def _builtin_ta_dema(self, args: list[Any]) -> list[float | None]:
        """Double Exponential Moving Average.

        ta.dema(series, length)
        DEMA = 2 * EMA - EMA(EMA)
        Reduces lag compared to simple EMA.
        Returns DEMA series.
        """
        if len(args) < 2:
            msg = "ta.dema() requires 2 arguments: series, length"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.dema length must be integer")

        ema1 = self._ema(series, length)
        ema2 = self._ema(ema1, length)

        dema_values = []
        for i in range(len(series)):
            if ema1[i] is None or ema2[i] is None:
                dema_values.append(None)
            else:
                dema_values.append(2 * ema1[i] - ema2[i])

        return dema_values

    def _builtin_ta_tema(self, args: list[Any]) -> list[float | None]:
        """Triple Exponential Moving Average.

        ta.tema(series, length)
        TEMA = 3 * EMA - 3 * EMA(EMA) + EMA(EMA(EMA))
        Even less lag than DEMA.
        Returns TEMA series.
        """
        if len(args) < 2:
            msg = "ta.tema() requires 2 arguments: series, length"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.tema length must be integer")

        ema1 = self._ema(series, length)
        ema2 = self._ema(ema1, length)
        ema3 = self._ema(ema2, length)

        tema_values = []
        for i in range(len(series)):
            if ema1[i] is None or ema2[i] is None or ema3[i] is None:
                tema_values.append(None)
            else:
                tema_values.append(3 * ema1[i] - 3 * ema2[i] + ema3[i])

        return tema_values

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

        fast_ema = self._ema(series, fast)
        slow_ema = self._ema(series, slow)

        apo_values = []
        for i in range(len(series)):
            if fast_ema[i] is None or slow_ema[i] is None:
                apo_values.append(None)
            else:
                apo_values.append(fast_ema[i] - slow_ema[i])

        return apo_values

    def _builtin_ta_stoch_smooth(self, args: list[Any]) -> list[float | None]:
        """Smoothed Stochastic Oscillator.

        ta.stoch_smooth(high, low, close, period, smooth_k, smooth_d)
        Stochastic with additional smoothing.
        Returns smoothed stochastic series.
        """
        if len(args) < 6:
            msg = "ta.stoch_smooth() requires 6 arguments: high, low, close, period, smooth_k, smooth_d"
            self._error(msg)

        high_series = args[0] if isinstance(args[0], list) else [args[0]]
        low_series = args[1] if isinstance(args[1], list) else [args[1]]
        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        period = self._expect_int(args[3], "ta.stoch_smooth period must be integer")
        smooth_k = self._expect_int(args[4], "ta.stoch_smooth smooth_k must be integer")
        smooth_d = self._expect_int(args[5], "ta.stoch_smooth smooth_d must be integer")

        # Calculate raw stochastic
        stoch_values = []
        for i in range(len(close_series)):
            start_idx = max(0, i - period + 1)
            high_max = max(high_series[j] for j in range(start_idx, i + 1) if j < len(high_series))
            low_min = min(low_series[j] for j in range(start_idx, i + 1) if j < len(low_series))
            c = close_series[i] if i < len(close_series) else 0

            hl_range = high_max - low_min
            if hl_range != 0:
                stoch = 100 * (c - low_min) / hl_range
            else:
                stoch = 50.0

            stoch_values.append(stoch)

        # Smooth stochastic
        smooth_k_ema = self._ema(stoch_values, smooth_k)
        smooth_d_ema = self._ema(smooth_k_ema, smooth_d)

        return smooth_d_ema

    def _builtin_ta_rsi_divergence(self, args: list[Any]) -> list[float | None]:
        """RSI Divergence Detector.

        ta.rsi_divergence(rsi_series, period)
        Detects bullish/bearish divergences in RSI.
        Returns divergence strength (-1 to 1).
        """
        if len(args) < 2:
            msg = "ta.rsi_divergence() requires 2 arguments: rsi_series, period"
            self._error(msg)

        rsi_series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "ta.rsi_divergence period must be integer")

        divergence_values = []
        for i in range(len(rsi_series)):
            if i < period:
                divergence_values.append(0.0)
                continue

            start_idx = max(0, i - period)
            rsi_values = [rsi_series[j] for j in range(start_idx, i + 1) if rsi_series[j] is not None]

            if len(rsi_values) < 2:
                divergence_values.append(0.0)
                continue

            rsi_min = min(rsi_values)
            rsi_max = max(rsi_values)
            rsi_range = rsi_max - rsi_min

            if rsi_range > 0:
                divergence = (rsi_series[i] - rsi_min) / rsi_range * 2 - 1
            else:
                divergence = 0.0

            divergence_values.append(divergence)

        return divergence_values

    def _builtin_ta_macd_signal(self, args: list[Any]) -> float | None:
        """MACD Signal Strength.

        ta.macd_signal(macd_line, signal_line)
        Measures MACD momentum (difference between MACD and signal).
        Returns signal strength.
        """
        if len(args) < 2:
            msg = "ta.macd_signal() requires 2 arguments: macd_line, signal_line"
            self._error(msg)

        macd_line = args[0]
        signal_line = args[1]

        if macd_line is None or signal_line is None:
            return None

        strength = float(macd_line) - float(signal_line)
        return strength

    # Phase 8 Tier 2: Medium-priority indicators

    def _builtin_ta_ichimoku(self, args: list[Any]) -> dict[str, float | None]:
        """Ichimoku Cloud Components.

        ta.ichimoku(fast_period, slow_period)
        Returns dict with tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b
        """
        if len(args) < 2:
            msg = "ta.ichimoku() requires 2 arguments: fast_period, slow_period"
            self._error(msg)

        fast_period = self._expect_int(args[0], "fast_period must be integer")
        slow_period = self._expect_int(args[1], "slow_period must be integer")

        if fast_period < 1 or slow_period < 1:
            msg = "Ichimoku periods must be >= 1"
            self._error(msg)

        # Get current high/low from context
        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

        if not highs or not lows:
            return {"tenkan_sen": None, "kijun_sen": None, "senkou_span_a": None, "senkou_span_b": None}

        # Tenkan-sen: 9-period high-low midpoint
        tenkan = None
        if len(highs) >= fast_period:
            fast_high = max(highs[-fast_period:])
            fast_low = min(lows[-fast_period:])
            tenkan = (fast_high + fast_low) / 2.0

        # Kijun-sen: 26-period high-low midpoint
        kijun = None
        if len(highs) >= slow_period:
            slow_high = max(highs[-slow_period:])
            slow_low = min(lows[-slow_period:])
            kijun = (slow_high + slow_low) / 2.0

        # Senkou Span A: midpoint of tenkan and kijun
        senkou_a = None
        if tenkan is not None and kijun is not None:
            senkou_a = (tenkan + kijun) / 2.0

        # Senkou Span B: 52-period high-low midpoint
        senkou_b = None
        if len(highs) >= 52:
            high_52 = max(highs[-52:])
            low_52 = min(lows[-52:])
            senkou_b = (high_52 + low_52) / 2.0

        return {"tenkan_sen": tenkan, "kijun_sen": kijun, "senkou_span_a": senkou_a, "senkou_span_b": senkou_b}

    def _builtin_ta_donchian(self, args: list[Any]) -> dict[str, float | None]:
        """Donchian Channels.

        ta.donchian(length)
        Returns dict with high, low, mid for specified period.
        """
        if len(args) < 1:
            msg = "ta.donchian() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < 1:
            msg = "Donchian length must be >= 1"
            self._error(msg)

        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

        if not highs or not lows or len(highs) < length:
            return {"high": None, "low": None, "mid": None}

        high_val = max(highs[-length:])
        low_val = min(lows[-length:])
        mid_val = (high_val + low_val) / 2.0

        return {"high": high_val, "low": low_val, "mid": mid_val}

    def _builtin_ta_stochrsi(self, args: list[Any]) -> dict[str, float | None]:
        """Stochastic RSI.

        ta.stochrsi(rsi_length, stoch_length)
        Returns dict with stochrsi value and signal.
        """
        if len(args) < 2:
            msg = "ta.stochrsi() requires 2 arguments: rsi_length, stoch_length"
            self._error(msg)

        rsi_length = self._expect_int(args[0], "rsi_length must be integer")
        stoch_length = self._expect_int(args[1], "stoch_length must be integer")

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < rsi_length:
            return {"stochrsi": None, "signal": None}

        # Calculate RSI series
        rsi_series = []
        for i in range(len(closes)):
            if i < rsi_length:
                rsi_series.append(None)
            else:
                segment = closes[i - rsi_length + 1 : i + 1]
                gains = sum(max(0, segment[j] - segment[j - 1]) for j in range(1, len(segment)))
                losses = sum(max(0, segment[j - 1] - segment[j]) for j in range(1, len(segment)))
                avg_gain = gains / rsi_length
                avg_loss = losses / rsi_length
                rs = avg_gain / avg_loss if avg_loss != 0 else 100.0
                rsi_val = 100.0 - (100.0 / (1.0 + rs))
                rsi_series.append(rsi_val)

        # Calculate StochRSI from RSI series
        valid_rsi = [v for v in rsi_series if v is not None]
        if len(valid_rsi) < stoch_length:
            return {"stochrsi": None, "signal": None}

        rsi_high = max(valid_rsi[-stoch_length:])
        rsi_low = min(valid_rsi[-stoch_length:])
        rsi_range = rsi_high - rsi_low

        if rsi_range == 0:
            stochrsi_val = 0.0
        else:
            stochrsi_val = (valid_rsi[-1] - rsi_low) / rsi_range * 100.0

        # Signal is EMA of StochRSI
        signal = stochrsi_val * 0.33 + (getattr(self, "_last_stochrsi_signal", stochrsi_val) * 0.67)
        self._last_stochrsi_signal = signal

        return {"stochrsi": stochrsi_val, "signal": signal}

    def _builtin_ta_dpo(self, args: list[Any]) -> float | None:
        """Detrended Price Oscillator.

        ta.dpo(length)
        Removes trend to identify cycles.
        """
        if len(args) < 1:
            msg = "ta.dpo() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < 1:
            msg = "DPO length must be >= 1"
            self._error(msg)

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < length:
            return None

        sma_val = sum(closes[-length:]) / length
        displacement = length // 2 + 1

        if len(closes) < displacement:
            return None

        dpo_val = closes[-displacement] - sma_val
        return dpo_val

    def _builtin_ta_kst(self, args: list[Any]) -> float | None:
        """Know Sure Thing Oscillator.

        ta.kst(length1, length2, length3, length4)
        Multi-timeframe momentum indicator.
        """
        if len(args) < 4:
            msg = "ta.kst() requires 4 arguments: length1, length2, length3, length4"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")
        length4 = self._expect_int(args[3], "length4 must be integer")

        closes = self.current_series.get("close", [])
        if not closes:
            return None

        max_len = max(length1, length2, length3, length4)
        if len(closes) < max_len:
            return None

        # Calculate ROCs (Rate of Change)
        roc1 = (closes[-1] - closes[-length1]) / closes[-length1] * 100 if len(closes) >= length1 else 0
        roc2 = (closes[-1] - closes[-length2]) / closes[-length2] * 100 if len(closes) >= length2 else 0
        roc3 = (closes[-1] - closes[-length3]) / closes[-length3] * 100 if len(closes) >= length3 else 0
        roc4 = (closes[-1] - closes[-length4]) / closes[-length4] * 100 if len(closes) >= length4 else 0

        # Weighted sum
        kst_val = roc1 * 1.0 + roc2 * 2.0 + roc3 * 3.0 + roc4 * 4.0
        return kst_val / 10.0

    def _builtin_ta_uo(self, args: list[Any]) -> float | None:
        """Ultimate Oscillator.

        ta.uo(length1, length2, length3)
        Multi-period momentum indicator.
        """
        if len(args) < 3:
            msg = "ta.uo() requires 3 arguments: length1, length2, length3"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")

        closes = self.current_series.get("close", [])
        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

        if not closes or not highs or not lows or len(closes) < length3:
            return None

        max_len = max(length1, length2, length3)

        # True Range and Buying Pressure
        tr_sum = 0.0
        bp_sum = 0.0
        for i in range(len(closes) - max_len, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i - 1]) if i > 0 else high_low
            low_close = abs(lows[i] - closes[i - 1]) if i > 0 else 0
            tr = max(high_low, high_close, low_close)

            bp = closes[i] - min(lows[i], closes[i - 1]) if i > 0 else 0
            tr_sum += tr
            bp_sum += bp

        if tr_sum == 0:
            return 0.0

        avg1 = bp_sum / tr_sum
        avg2 = bp_sum / tr_sum
        avg3 = bp_sum / tr_sum

        uo_val = 100.0 * ((avg1 * 4.0 + avg2 * 2.0 + avg3) / 7.0)
        return uo_val

    def _builtin_ta_bb_pct(self, args: list[Any]) -> float | None:
        """Bollinger Band Percentage.

        ta.bb_pct(length, std_dev)
        Position between upper and lower bands (0-100).
        """
        if len(args) < 2:
            msg = "ta.bb_pct() requires 2 arguments: length, std_dev"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")
        std_dev = float(args[1]) if isinstance(args[1], (int, float)) else 2.0

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < length:
            return None

        sma_val = sum(closes[-length:]) / length
        variance = sum((v - sma_val) ** 2 for v in closes[-length:]) / length
        std_val = variance ** 0.5

        upper = sma_val + (std_val * std_dev)
        lower = sma_val - (std_val * std_dev)

        if upper == lower:
            return 50.0

        bb_pct = ((closes[-1] - lower) / (upper - lower)) * 100.0
        return max(0.0, min(100.0, bb_pct))

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

        # VPT = Previous VPT + Volume * (Price Change / Previous Price)
        prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
        if prev_close == 0:
            return 0.0

        price_change_pct = (closes[-1] - prev_close) / prev_close
        vpt_val = volumes[-1] * price_change_pct

        return vpt_val

    def _builtin_ta_beta(self, args: list[Any]) -> float | None:
        """Beta Coefficient.

        ta.beta(series1, series2, length)
        Correlation measure between two series.
        """
        if len(args) < 3:
            msg = "ta.beta() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        mean1 = sum(s1) / length
        mean2 = sum(s2) / length

        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(length)) / length
        variance2 = sum((v - mean2) ** 2 for v in s2) / length

        if variance2 == 0:
            return 0.0

        beta_val = covariance / variance2
        return beta_val

    def _builtin_ta_r_squared(self, args: list[Any]) -> float | None:
        """R-Squared (Coefficient of Determination).

        ta.r_squared(series1, series2, length)
        Measures fit quality (0-1).
        """
        if len(args) < 3:
            msg = "ta.r_squared() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        mean1 = sum(s1) / length
        mean2 = sum(s2) / length

        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(length)) / length
        var1 = sum((v - mean1) ** 2 for v in s1) / length
        var2 = sum((v - mean2) ** 2 for v in s2) / length

        if var1 == 0 or var2 == 0:
            return 0.0

        correlation = covariance / ((var1 * var2) ** 0.5)
        r_squared = correlation ** 2

        return max(0.0, min(1.0, r_squared))

    def _builtin_ta_comovement(self, args: list[Any]) -> float | None:
        """Comovement Index.

        ta.comovement(series1, series2, length)
        Synchronicity between two series.
        """
        if len(args) < 3:
            msg = "ta.comovement() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        same_direction = sum(1 for i in range(1, length) if (s1[i] - s1[i - 1]) * (s2[i] - s2[i - 1]) > 0)

        comovement = (same_direction / (length - 1)) * 100.0 if length > 1 else 0.0
        return comovement

    def _builtin_ta_atr_stop(self, args: list[Any]) -> dict[str, float | None]:
        """ATR-based Stop Loss.

        ta.atr_stop(atr_value, multiplier)
        Calculate stop levels based on ATR.
        """
        if len(args) < 2:
            msg = "ta.atr_stop() requires 2 arguments: atr_value, multiplier"
            self._error(msg)

        atr_val = float(args[0]) if isinstance(args[0], (int, float)) else None
        multiplier = float(args[1]) if isinstance(args[1], (int, float)) else 2.0

        if atr_val is None or atr_val <= 0:
            return {"long_stop": None, "short_stop": None}

        closes = self.current_series.get("close", [])
        if not closes:
            return {"long_stop": None, "short_stop": None}

        current_close = closes[-1]
        long_stop = current_close - (atr_val * multiplier)
        short_stop = current_close + (atr_val * multiplier)

        return {"long_stop": long_stop, "short_stop": short_stop}

    def _builtin_ta_fractal(self, args: list[Any]) -> dict[str, bool]:
        """Fractal Pattern Detector.

        ta.fractal(period)
        Identifies high/low fractals.
        """
        if len(args) < 1:
            msg = "ta.fractal() requires 1 argument: period"
            self._error(msg)

        period = self._expect_int(args[0], "period must be integer")

        if period < 1:
            msg = "Fractal period must be >= 1"
            self._error(msg)

        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

        if not highs or not lows or len(highs) < period * 2 + 1:
            return {"is_high_fractal": False, "is_low_fractal": False}

        # Check if current bar is a high fractal
        current_idx = len(highs) - 1
        is_high_fractal = highs[current_idx] == max(highs[current_idx - period : current_idx + period + 1])

        # Check if current bar is a low fractal
        is_low_fractal = lows[current_idx] == min(lows[current_idx - period : current_idx + period + 1])

        return {"is_high_fractal": is_high_fractal, "is_low_fractal": is_low_fractal}

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

        emv_vals = []
        for i in range(len(highs)):
            if i == 0 or volumes[i] == 0:
                emv_vals.append(None)
                continue

            distance_moved = ((highs[i] + lows[i]) / 2.0) - ((highs[i - 1] + lows[i - 1]) / 2.0)
            box_height = highs[i] - lows[i]

            if box_height == 0:
                emv_vals.append(None)
            else:
                emv = (distance_moved / box_height) * (highs[i] - lows[i]) / volumes[i] if volumes[i] != 0 else 0
                emv_vals.append(emv)

        valid_emv = [v for v in emv_vals if v is not None]
        if not valid_emv or len(valid_emv) < length:
            return None

        emv_sma = sum(valid_emv[-length:]) / length
        return emv_sma

    # Phase 8 Tier 3: Specialized indicators

    def _builtin_ta_engulfing(self, args: list[Any]) -> dict[str, int | bool]:
        """Engulfing Pattern Detector.

        ta.engulfing(open, high, low, close)
        Identifies bullish/bearish engulfing patterns.
        """
        if len(args) < 4:
            msg = "ta.engulfing() requires 4 arguments: open, high, low, close"
            self._error(msg)

        opens = args[0] if isinstance(args[0], list) else [args[0]]
        closes = args[3] if isinstance(args[3], list) else [args[3]]

        if len(opens) < 2 or len(closes) < 2:
            return {"is_bullish": False, "is_bearish": False, "pattern_strength": 0.0}

        current_open = opens[-1]
        current_close = closes[-1]

        prev_open = opens[-2]
        prev_close = closes[-2]

        # Bullish engulfing: current candle engulfs previous and is green
        is_bullish = (current_open < prev_close and current_close > prev_open and
                      current_close > current_open)

        # Bearish engulfing: current candle engulfs previous and is red
        is_bearish = (current_open > prev_close and current_close < prev_open and
                      current_close < current_open)

        # Pattern strength (0-1) based on how much body engulfed
        if is_bullish:
            engulf_amount = max(0, min(1, (current_close - prev_open) / abs(prev_open - prev_close + 0.0001)))
        elif is_bearish:
            engulf_amount = max(0, min(1, (prev_open - current_close) / abs(prev_close - prev_open + 0.0001)))
        else:
            engulf_amount = 0.0

        return {"is_bullish": is_bullish, "is_bearish": is_bearish, "pattern_strength": engulf_amount}

    def _builtin_ta_hammer(self, args: list[Any]) -> dict[str, bool | float]:
        """Hammer/Doji Pattern Detector.

        ta.hammer(open, high, low, close)
        Identifies hammer and doji patterns.
        """
        if len(args) < 4:
            msg = "ta.hammer() requires 4 arguments: open, high, low, close"
            self._error(msg)

        opens = args[0] if isinstance(args[0], list) else [args[0]]
        highs = args[1] if isinstance(args[1], list) else [args[1]]
        lows = args[2] if isinstance(args[2], list) else [args[2]]
        closes = args[3] if isinstance(args[3], list) else [args[3]]

        if not opens or not closes:
            return {"is_hammer": False, "is_doji": False, "pattern_strength": 0.0}

        current_open = opens[-1]
        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        body_size = abs(current_close - current_open)
        total_range = current_high - current_low
        lower_wick = min(current_open, current_close) - current_low
        upper_wick = current_high - max(current_open, current_close)

        # Doji: open ~= close
        is_doji = body_size < total_range * 0.1

        # Hammer: small body, long lower wick, short upper wick
        is_hammer = (
            body_size > 0 and
            lower_wick > body_size * 2 and
            upper_wick < body_size
        )

        # Pattern strength
        if is_doji:
            strength = 1.0 - (body_size / (total_range + 0.0001))
        elif is_hammer:
            strength = min(1.0, lower_wick / (total_range + 0.0001))
        else:
            strength = 0.0

        return {"is_hammer": is_hammer, "is_doji": is_doji, "pattern_strength": strength}

    def _builtin_ta_gap_detector(self, args: list[Any]) -> dict[str, float | int]:
        """Gap Pattern Detector.

        ta.gap_detector(high, low, prev_close)
        Identifies and measures price gaps.
        """
        if len(args) < 3:
            msg = "ta.gap_detector() requires 3 arguments: high, low, prev_close"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]
        prev_close = float(args[2]) if isinstance(args[2], (int, float)) else None

        if not highs or not lows or prev_close is None:
            return {"gap_size": 0.0, "gap_type": 0, "gap_percent": 0.0}

        current_high = highs[-1]
        current_low = lows[-1]

        # Upside gap: current low > prev close
        upside_gap = max(0, current_low - prev_close)

        # Downside gap: current high < prev close
        downside_gap = max(0, prev_close - current_high)

        if upside_gap > downside_gap:
            gap_size = upside_gap
            gap_type = 1  # Upside
            gap_percent = (upside_gap / prev_close * 100) if prev_close != 0 else 0.0
        elif downside_gap > 0:
            gap_size = downside_gap
            gap_type = -1  # Downside
            gap_percent = (downside_gap / prev_close * 100) if prev_close != 0 else 0.0
        else:
            gap_size = 0.0
            gap_type = 0  # No gap
            gap_percent = 0.0

        return {"gap_size": gap_size, "gap_type": gap_type, "gap_percent": gap_percent}

    def _builtin_ta_voi(self, args: list[Any]) -> float:
        """Volume of Imbalance.

        ta.voi(buy_volume, sell_volume)
        Measures imbalance in buy vs sell volume.
        """
        if len(args) < 2:
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
        if len(args) < 4:
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

    def _builtin_ta_expected_value(self, args: list[Any]) -> float:
        """Expected Value.

        ta.expected_value(returns, probabilities)
        Calculates statistical expected value.
        """
        if len(args) < 2:
            msg = "ta.expected_value() requires 2 arguments: returns, probabilities"
            self._error(msg)

        returns = args[0] if isinstance(args[0], list) else [args[0]]
        probs = args[1] if isinstance(args[1], list) else [args[1]]

        if len(returns) != len(probs):
            msg = "Returns and probabilities must have same length"
            self._error(msg)

        total_prob = sum(p for p in probs if isinstance(p, (int, float)))
        if total_prob == 0:
            return 0.0

        ev = sum(
            (r if isinstance(r, (int, float)) else 0.0) * (p if isinstance(p, (int, float)) else 0.0)
            for r, p in zip(returns, probs)
        )
        return ev / total_prob

    def _builtin_ta_skewness(self, args: list[Any]) -> float | None:
        """Skewness.

        ta.skewness(series, period)
        Measures asymmetry in distribution.
        """
        if len(args) < 2:
            msg = "ta.skewness() requires 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        mean = sum(valid_data) / len(valid_data)
        variance = sum((x - mean) ** 2 for x in valid_data) / len(valid_data)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Skewness = E[(x - mean)³] / std_dev³
        skewness_val = sum((x - mean) ** 3 for x in valid_data) / (len(valid_data) * (std_dev ** 3))
        return skewness_val

    def _builtin_ta_kurtosis(self, args: list[Any]) -> float | None:
        """Kurtosis.

        ta.kurtosis(series, period)
        Measures tail risk and peakedness.
        """
        if len(args) < 2:
            msg = "ta.kurtosis() requires 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        mean = sum(valid_data) / len(valid_data)
        variance = sum((x - mean) ** 2 for x in valid_data) / len(valid_data)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Kurtosis = E[(x - mean)⁴] / std_dev⁴ - 3
        fourth_moment = sum((x - mean) ** 4 for x in valid_data) / len(valid_data)
        kurtosis_val = (fourth_moment / (std_dev ** 4)) - 3.0
        return kurtosis_val

    def _builtin_ta_parkinson(self, args: list[Any]) -> float | None:
        """Parkinson Volatility.

        ta.parkinson(high, low)
        Calculates volatility from high-low range.
        """
        if len(args) < 2:
            msg = "ta.parkinson() requires 2 arguments: high, low"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]

        if not highs or not lows or len(highs) == 0:
            return None

        current_high = highs[-1] if isinstance(highs[-1], (int, float)) else None
        current_low = lows[-1] if isinstance(lows[-1], (int, float)) else None

        if current_high is None or current_low is None or current_high <= current_low:
            return None

        ratio = current_high / current_low
        if ratio <= 0:
            return None

        # Parkinson volatility
        import math
        parkinson_vol = math.sqrt(math.log(ratio) ** 2 / (4 * math.log(2)))
        return parkinson_vol

    def _builtin_ta_garman_klass(self, args: list[Any]) -> float | None:
        """Garman-Klass Volatility.

        ta.garman_klass(high, low, close, open)
        Volatility using OHLC data.
        """
        if len(args) < 4:
            msg = "ta.garman_klass() requires 4 arguments: high, low, close, open"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]
        closes = args[2] if isinstance(args[2], list) else [args[2]]
        opens = args[3] if isinstance(args[3], list) else [args[3]]

        if not highs or not lows or not closes or not opens:
            return None

        h = highs[-1] if isinstance(highs[-1], (int, float)) else None
        l = lows[-1] if isinstance(lows[-1], (int, float)) else None
        c = closes[-1] if isinstance(closes[-1], (int, float)) else None
        o = opens[-1] if isinstance(opens[-1], (int, float)) else None

        if h is None or l is None or c is None or o is None:
            return None

        if h <= l or h <= 0 or c <= 0:
            return None

        import math

        # Garman-Klass volatility formula
        hl_ratio = h / l
        co_ratio = c / o

        term1 = 0.5 * (math.log(hl_ratio) ** 2)
        term2 = (2 * math.log(2) - 1) * (math.log(co_ratio) ** 2)

        gk_vol = math.sqrt(term1 - term2)
        return gk_vol

    # Phase 8 Tier 4: Enhancement Variants

    def _builtin_ta_sma_weighted(self, args: list[Any]) -> float | None:
        """Weighted SMA - Simple Moving Average with custom weighting.

        ta.sma_weighted(series, period, weight_type)
        Applies different weighting schemes to SMA calculation.
        weight_type: "linear", "quadratic", "sqrt" (default: "linear")
        """
        if len(args) < 2:
            msg = "ta.sma_weighted() requires at least 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")
        weight_type = args[2] if len(args) > 2 else "linear"

        if not isinstance(weight_type, str):
            weight_type = "linear"

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        # Calculate weights based on type
        weights = []
        for i in range(len(valid_data)):
            if weight_type == "quadratic":
                weight = (i + 1) ** 2
            elif weight_type == "sqrt":
                weight = (i + 1) ** 0.5
            else:  # linear (default)
                weight = i + 1
            weights.append(weight)

        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(v * w for v, w in zip(valid_data, weights, strict=True))
        return weighted_sum / total_weight if total_weight > 0 else None

    def _builtin_ta_ema_cross_signal(self, args: list[Any]) -> dict:
        """EMA Cross Signal - Detects EMA crossover/crossunder signals.

        ta.ema_cross_signal(close, fast_period, slow_period)
        Returns signal information for EMA crossovers.
        """
        if len(args) < 3:
            msg = "ta.ema_cross_signal() requires 3 arguments: close, fast_period, slow_period"
            self._error(msg)

        close_series = args[0] if isinstance(args[0], list) else [args[0]]
        fast_period = self._expect_int(args[1], "fast_period must be integer")
        slow_period = self._expect_int(args[2], "slow_period must be integer")

        if len(close_series) < max(fast_period, slow_period):
            return {"crossover": False, "crossunder": False, "signal": 0}

        # Calculate EMAs
        fast_ema_list = self._ema(close_series, fast_period)
        slow_ema_list = self._ema(close_series, slow_period)

        if not fast_ema_list or not slow_ema_list:
            return {"crossover": False, "crossunder": False, "signal": 0}

        fast_current = fast_ema_list[-1] if fast_ema_list[-1] is not None else None
        fast_prev = fast_ema_list[-2] if len(fast_ema_list) > 1 and fast_ema_list[-2] is not None else None
        slow_current = slow_ema_list[-1] if slow_ema_list[-1] is not None else None
        slow_prev = slow_ema_list[-2] if len(slow_ema_list) > 1 and slow_ema_list[-2] is not None else None

        if fast_current is None or slow_current is None or fast_prev is None or slow_prev is None:
            return {"crossover": False, "crossunder": False, "signal": 0}

        # Detect crossover (fast crosses above slow)
        crossover = fast_prev <= slow_prev and fast_current > slow_current
        # Detect crossunder (fast crosses below slow)
        crossunder = fast_prev >= slow_prev and fast_current < slow_current
        # Signal: 1 for bullish cross, -1 for bearish cross, 0 for none
        signal = 1 if crossover else (-1 if crossunder else 0)

        return {"crossover": crossover, "crossunder": crossunder, "signal": signal}

    def _builtin_ta_rsi_oversold_overbought(self, args: list[Any]) -> dict:
        """RSI Oversold/Overbought Levels - Custom RSI threshold detection.

        ta.rsi_oversold_overbought(rsi_series, oversold_level, overbought_level)
        Returns boolean flags for oversold/overbought conditions.
        """
        if len(args) < 3:
            msg = "ta.rsi_oversold_overbought() requires 3 arguments: rsi_series, oversold, overbought"
            self._error(msg)

        rsi_series = args[0] if isinstance(args[0], list) else [args[0]]
        oversold = self._expect_int(args[1], "oversold must be integer")
        overbought = self._expect_int(args[2], "overbought must be integer")

        if not rsi_series or len(rsi_series) == 0:
            return {"is_oversold": False, "is_overbought": False, "rsi": None}

        rsi_current = rsi_series[-1]
        if rsi_current is None:
            return {"is_oversold": False, "is_overbought": False, "rsi": None}

        is_oversold = rsi_current < oversold
        is_overbought = rsi_current > overbought

        return {"is_oversold": is_oversold, "is_overbought": is_overbought, "rsi": rsi_current}

    def _builtin_ta_atr_normalized(self, args: list[Any]) -> float | None:
        """Normalized ATR - ATR as percentage of current price.

        ta.atr_normalized(high, low, close, period)
        Returns ATR as a percentage of price for comparable analysis.
        """
        if len(args) < 4:
            msg = "ta.atr_normalized() requires 4 arguments: high, low, close, period"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]
        closes = args[2] if isinstance(args[2], list) else [args[2]]
        period = self._expect_int(args[3], "period must be integer")

        if len(closes) == 0 or not isinstance(closes[-1], (int, float)):
            return None

        current_close = closes[-1]
        if current_close == 0:
            return None

        # Calculate ATR
        atr_list = self._atr(highs, lows, closes, period)
        if not atr_list or atr_list[-1] is None:
            return None

        atr_current = atr_list[-1]
        # Normalized ATR as percentage
        normalized_atr = (atr_current / current_close) * 100
        return normalized_atr

    def _builtin_ta_volume_weighted_momentum(self, args: list[Any]) -> float | None:
        """Volume-Weighted Momentum - Momentum adjusted for volume.

        ta.volume_weighted_momentum(close, volume, period)
        Combines price momentum with volume strength for weighted signal.
        """
        if len(args) < 3:
            msg = "ta.volume_weighted_momentum() requires 3 arguments: close, volume, period"
            self._error(msg)

        close_series = args[0] if isinstance(args[0], list) else [args[0]]
        volume_series = args[1] if isinstance(args[1], list) else [args[1]]
        period = self._expect_int(args[2], "period must be integer")

        if len(close_series) < period or len(volume_series) < period:
            return None

        close_data = close_series[-period:]
        volume_data = volume_series[-period:]

        # Filter valid data
        valid_pairs = [
            (c, v)
            for c, v in zip(close_data, volume_data, strict=True)
            if isinstance(c, (int, float))
            and isinstance(v, (int, float))
            and v > 0
        ]

        if len(valid_pairs) < 2:
            return None

        # Calculate price change and weighted momentum
        weighted_momentum = 0.0
        total_volume = sum(v for c, v in valid_pairs)

        for i in range(1, len(valid_pairs)):
            price_change = valid_pairs[i][0] - valid_pairs[i - 1][0]
            volume_weight = valid_pairs[i][1] / total_volume if total_volume > 0 else 0
            weighted_momentum += price_change * volume_weight

        return weighted_momentum


