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
        }

    # -- Public entry points -------------------------------------------------

    def _builtin_ta_sma(self, args: list[Any]) -> list[float]:
        series, period = self._expect_series(args, length=2)
        return self._sma(series, period)

    def _builtin_ta_ema(self, args: list[Any]) -> list[float]:
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

    def _builtin_ta_atr(self, args: list[Any]) -> list[float]:
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

    def _builtin_ta_vwma(self, args: list[Any]) -> list[float]:
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

    def _sma(self, series: list[Any], period: int) -> list[float]:
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

    def _ema(self, series: list[Any], period: int) -> list[float]:
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
    ) -> list[float]:
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

        highs = self._expect_series(args[0], "ta.dmi takes high, low, close series and length")
        lows = self._expect_series(args[1], "ta.dmi takes high, low, close series and length")
        closes = self._expect_series(args[2], "ta.dmi takes high, low, close series and length")
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

        highs = self._expect_series(args[0], "ta.kc takes high, low, close series, length")
        lows = self._expect_series(args[1], "ta.kc takes high, low, close series, length")
        closes = self._expect_series(args[2], "ta.kc takes high, low, close series, length")
        length = self._expect_int(args[3] if len(args) > 3 else args[2], "ta.kc length must be integer")
        offset_percent = 1.0 if len(args) < 4 else (args[3] if isinstance(args[3], (int, float)) else 1.0)

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
        if len(args) != BINARY:
            self._error("ta.linreg takes source series and length")

        series = self._expect_series(args[0], "ta.linreg takes source series and length")
        length = self._expect_int(args[1], "ta.linreg takes source series and length")

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

        series = self._expect_series(args[0], "ta.rci takes source series and length")
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

        highs = self._expect_series(args[0], "ta.supertrend takes high, low, length, multiplier")
        lows = self._expect_series(args[1], "ta.supertrend takes high, low, length, multiplier")
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
        if len(args) != BINARY:
            self._error("ta.swma takes source series and length")

        series = self._expect_series(args[0], "ta.swma takes source series and length")
        length = self._expect_int(args[1], "ta.swma takes source series and length")

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

        series = self._expect_series(args[0], "ta.zigzag takes source series and percent threshold")
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
