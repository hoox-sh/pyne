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

"""Basic technical indicators module - MA, Crossover, Volatility, etc."""

from __future__ import annotations

import math
import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import QUINARY
from .core import TERNARY
from .core import UNARY
from .core import TechnicalHelpers


class BasicIndicators(TechnicalHelpers):
    """Basic technical indicators and moving averages."""

    # -- Public API (builtin_ta_ prefix) ------------------------------------

    def _builtin_ta_sma(self, args: list[Any]) -> list[float | None]:
        """Simple Moving Average."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._sma_inc_update(series, period)
        return self._finalize_series(self._sma(series, period))

    def _builtin_ta_ema(self, args: list[Any]) -> list[float | None]:
        """Exponential Moving Average."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._ema_inc_update(series, period)
        return self._finalize_series(self._ema(series, period))

    def _builtin_ta_wma(self, args: list[Any]) -> float | None:
        """Weighted Moving Average."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._wma_inc_update(series, period)
        return self._wma(series, period)

    def _builtin_ta_rma(self, args: list[Any]) -> list[float]:
        """Rolling Moving Average."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._rma_inc_update(series, period)
        return self._finalize_series(self._rma(series, period))

    def _builtin_ta_vwma(self, args: list[Any]) -> list[float | None]:
        """Volume Weighted Moving Average.

        ``ta.vwma(source, length)``, ``ta.vwma(length)``, or community
        ``ta.vwma(source, volume, length)``.
        """
        if len(args) == 1 and self._is_period_like(args[0]):
            period = self._expect_int(args[0], "Period must be an integer")
            if self._use_incremental_ta():
                series = self._context_source("close")
                vol = self._context_source("volume")
                if vol:
                    return self._vwma_inc_update(series, vol, period)
            series = self._context_series("close")
            return self._finalize_series(self._vwma(series, period))
        if len(args) == 3:
            period = self._expect_int(args[2], "Period must be an integer")
            if self._use_incremental_ta():
                series = args[0]
                vol = args[1] if not self._is_period_like(args[1]) else self._context_source("volume")
                if vol:
                    return self._vwma_inc_update(series, vol, period)
            series = self._as_series(args[0])
            vol = self._as_series(args[1]) if not self._is_period_like(args[1]) else self._context_series("volume")
            if self._use_incremental_ta() and vol:
                return self._vwma_inc_update(series, vol, period)
            return self._finalize_series(self._vwma(series, period))
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            vol = self._context_source("volume")
            if vol:
                return self._vwma_inc_update(series, vol, period)
        vol = self._context_series("volume")
        if self._use_incremental_ta() and vol:
            return self._vwma_inc_update(series, vol, period)
        return self._finalize_series(self._vwma(series, period))

    def _builtin_ta_hma(self, args: list[Any]) -> float | None:
        """Hull Moving Average."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._hma_inc_update(series, period)
        return self._hma(series, period)

    def _builtin_ta_vwap(self, args: list[Any]) -> float | None:
        """Volume Weighted Average Price.

        TradingView: ``ta.vwap(source)`` or ``ta.vwap`` (defaults to hlc3).
        Extra anchor/args beyond the source are ignored for now.
        """
        if self._use_incremental_ta():
            # O(1) cumulative — only need last price/volume samples.
            if len(args) == 0:
                series_map = getattr(self, "current_series", None) or {}
                source = series_map.get("hlc3") or series_map.get("close")
            else:
                source = args[0]
            if source is None or source == []:
                return None
            series_map = getattr(self, "current_series", None) or {}
            volume = series_map.get("volume")
            return self._vwap_inc_update(source, volume if volume else None)
        if len(args) == 0:
            source = self._context_series("hlc3") or self._context_series("close")
        else:
            source = self._as_series(args[0])
        volume = self._context_series("volume")
        if not source:
            return None
        # Align volume length
        if len(volume) < len(source):
            volume = volume + [0.0] * (len(source) - len(volume))
        # Cumulative VWAP over available history
        cum_pv = 0.0
        cum_v = 0.0
        last = None
        for i, price in enumerate(source):
            if price is None:
                continue
            v = volume[i] if i < len(volume) and volume[i] is not None else 0.0
            try:
                v = float(v)
                price = float(price)
            except (TypeError, ValueError):
                continue
            cum_pv += price * v
            cum_v += v
            last = (cum_pv / cum_v) if cum_v else price
        return last

    def _builtin_ta_crossover(self, args: list[Any]) -> bool:
        """Crossover check (works with full series or bar-mode last-sample)."""
        if self._use_incremental_ta():
            # Skip PineSeries reverse; stateful prev pair ≡ list[-2]/[-1]
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=False)
        series1, series2 = self._expect_two_series(args)
        if len(series1) >= 2 and len(series2) >= 2:
            return self._crossover(series1, series2)
        return self._cross_stateful(series1, series2, under=False)

    def _builtin_ta_crossunder(self, args: list[Any]) -> bool:
        """Crossunder check (works with full series or bar-mode last-sample)."""
        if self._use_incremental_ta():
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=True)
        series1, series2 = self._expect_two_series(args)
        if len(series1) >= 2 and len(series2) >= 2:
            return self._crossunder(series1, series2)
        return self._cross_stateful(series1, series2, under=True)

    def _builtin_ta_cross(self, args: list[Any]) -> bool:
        """Cross check (either direction)."""
        if self._use_incremental_ta():
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=False, either=True)
        series1, series2 = self._expect_two_series(args)
        return self._cross(series1, series2)

    def _builtin_ta_falling(self, args: list[Any]) -> bool:
        """Falling check."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._falling_inc_update(series, period)
        # Bar-mode locals are last-sample scalars (len 1) — full `_falling` needs
        # ``period`` samples; use call-site window (same as inc path).
        if self._bar_mode() and len(series) < period:
            return self._falling_inc_update(series, period)
        return self._falling(series, period)

    def _builtin_ta_rising(self, args: list[Any]) -> bool:
        """Rising check."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._rising_inc_update(series, period)
        if self._bar_mode() and len(series) < period:
            return self._rising_inc_update(series, period)
        return self._rising(series, period)

    def _builtin_ta_highest(self, args: list[Any]) -> Any:
        """Highest value. ``ta.highest(source, length)`` or ``ta.highest(length)`` → high."""
        series, period = self._expect_series(
            args,
            length=BINARY,
            default_source="high",
            allow_period_only=True,
            last_sample_ok=True,
        )
        if self._use_incremental_ta():
            return self._highest_inc_update(series, period)
        return self._highest(series, period)

    def _builtin_ta_lowest(self, args: list[Any]) -> Any:
        """Lowest value. ``ta.lowest(source, length)`` or ``ta.lowest(length)`` → low."""
        series, period = self._expect_series(
            args,
            length=BINARY,
            default_source="low",
            allow_period_only=True,
            last_sample_ok=True,
        )
        if self._use_incremental_ta():
            return self._lowest_inc_update(series, period)
        return self._lowest(series, period)

    def _builtin_ta_highestbars(self, args: list[Any]) -> int:
        """Offset to highest value."""
        if self._use_incremental_ta():
            if len(args) == 1 and self._is_period_like(args[0]):
                period = self._expect_int(args[0], "Period must be an integer")
                src = (getattr(self, "current_series", None) or {}).get("high") or []
            elif len(args) >= BINARY:
                period = self._expect_int(args[1], "Second argument must be an integer (period)")
                src = args[0]
            else:
                series, period = self._expect_series(
                    args, length=BINARY, default_source="high", allow_period_only=True
                )
                src = series
            return self._highestbars_inc_update(src, period)
        series, period = self._expect_series(
            args, length=BINARY, default_source="high", allow_period_only=True
        )
        # Derived locals may be last-sample only; keep call-site window in bar mode.
        if self._bar_mode() and len(series) < period:
            return self._highestbars_inc_update(series, period)
        return self._highestbars(series, period)

    def _builtin_ta_lowestbars(self, args: list[Any]) -> int:
        """Offset to lowest value."""
        if self._use_incremental_ta():
            if len(args) == 1 and self._is_period_like(args[0]):
                period = self._expect_int(args[0], "Period must be an integer")
                src = (getattr(self, "current_series", None) or {}).get("low") or []
            elif len(args) >= BINARY:
                period = self._expect_int(args[1], "Second argument must be an integer (period)")
                src = args[0]
            else:
                series, period = self._expect_series(
                    args, length=BINARY, default_source="low", allow_period_only=True
                )
                src = series
            return self._lowestbars_inc_update(src, period)
        series, period = self._expect_series(
            args, length=BINARY, default_source="low", allow_period_only=True
        )
        if self._bar_mode() and len(series) < period:
            return self._lowestbars_inc_update(series, period)
        return self._lowestbars(series, period)

    def _builtin_ta_change(self, args: list[Any]) -> float | None:
        """Change over period (1 or 2 args; period defaults to 1)."""
        if len(args) < 1 or len(args) > 2:
            self._error("ta.change() requires 1 or 2 arguments: source, (period)")
        period = self._expect_int(args[1], "Second argument must be an integer") if len(args) > 1 else 1
        if isinstance(period, float) and period == int(period):
            period = int(period)
        if self._use_incremental_ta():
            return self._change_inc_update(args[0], period)
        source = self._as_series(args[0])
        return self._change(source, period)

    def _builtin_ta_mom(self, args: list[Any]) -> float:
        """Momentum."""
        if self._use_incremental_ta():
            if len(args) != BINARY:
                self._error("ta.mom requires series and period")
            period = self._expect_int(args[1], "Second argument must be an integer (period)")
            return self._mom_inc_update(args[0], period)
        series, period = self._expect_series(args, length=BINARY)
        return self._mom(series, period)

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        """Standard Deviation."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._stdev_inc_update(series, period)
        return self._stdev(series, period)

    def _builtin_ta_swma(self, args: list[Any]) -> float | None:
        """Symmetrically Weighted Moving Average. TV: ``ta.swma(source)``."""
        if len(args) != UNARY:
            self._error("ta.swma expects one source argument")
        if self._use_incremental_ta():
            return self._swma_inc_update(args[0])
        return self._swma(self._as_series(args[0]))

    def _builtin_ta_tr(self, args: list[Any]) -> Any:
        """True Range.

        TradingView: ``ta.tr(handle_na)`` with 0–1 args (uses high/low/close
        from context). Also accepts the legacy 3-arg form for unit tests.
        """
        if len(args) <= UNARY:
            # Optional boolean handle_na is ignored for computation; na bars
            # already yield None via _tr internals.
            if self._use_incremental_ta():
                return self._tr_inc_update(
                    self._context_source("high"),
                    self._context_source("low"),
                    self._context_source("close"),
                )
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            return self._finalize_series(self._tr(highs, lows, closes))
        msg = "ta.tr expects high, low, and close (or 0–1 handle_na args)"
        if len(args) != TERNARY:
            self._error(msg)
        if self._use_incremental_ta():
            return self._tr_inc_update(args[0], args[1], args[2])
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        return self._finalize_series(self._tr(highs, lows, closes))

    def _builtin_ta_sar(self, args: list[Any]) -> Any:
        """Parabolic SAR. TV: ``ta.sar(start, inc, max)`` using high/low context."""
        if len(args) == TERNARY and all(isinstance(a, (int, float)) and not isinstance(a, bool) for a in args):
            start = float(args[0])
            increment = float(args[1])
            maximum = float(args[2])
            if self._use_incremental_ta():
                return self._sar_inc_update(
                    self._context_source("high"),
                    self._context_source("low"),
                    start,
                    increment,
                    maximum,
                )
            highs = self._context_series("high")
            lows = self._context_series("low")
            return self._finalize_series(self._sar(highs, lows, start, increment, maximum))
        msg = "ta.sar expects start, increment, max (or high, low, start, increment, max)"
        if len(args) != QUINARY:
            self._error(msg)
        start = self._expect_number(args[2], msg)
        increment = self._expect_number(args[3], msg)
        maximum = self._expect_number(args[4], msg)
        if self._use_incremental_ta():
            return self._sar_inc_update(args[0], args[1], start, increment, maximum)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        return self._finalize_series(self._sar(highs, lows, start, increment, maximum))

    def _builtin_ta_bb(
        self,
        args: list[Any],
    ) -> tuple[float | None, float | None, float | None]:
        """Bollinger Bands. ``ta.bb(source, length, mult)`` or ``ta.bb(length, mult)``."""
        msg = "ta.bb expects series, length, and multiplier"
        if len(args) == BINARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], msg)
            multiplier = args[1]
            series = (
                self._context_source("close")
                if self._use_incremental_ta()
                else self._context_series("close")
            )
        elif len(args) == TERNARY:
            length = self._expect_int(args[1], msg)
            multiplier = args[2]
            # Inc path: last-sample only (``_series_last``). Full path needs chrono list.
            series = self._as_series_or_raw(args[0], last_sample_ok=True)
        else:
            self._error(msg)
            return None, None, None
        if hasattr(multiplier, "current") and not isinstance(multiplier, (list, tuple, str, bytes, int, float)):
            multiplier = multiplier.current
        if not isinstance(multiplier, int | float):
            self._error("ta.bb expects numeric multiplier")
        if self._use_incremental_ta():
            return self._bb_inc_update(series, length, float(multiplier))
        return self._bollinger_bands(series, length, multiplier)

    def _builtin_ta_atr(self, args: list[Any]) -> Any:
        """Average True Range. TV: ``ta.atr(length)``; also legacy 4-arg form."""
        if len(args) == 1 and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.atr length must be an integer")
            if self._use_incremental_ta():
                return self._atr_inc_update(
                    self._context_source("high"),
                    self._context_source("low"),
                    self._context_source("close"),
                    length,
                )
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            return self._finalize_series(self._atr(highs, lows, closes, length))
        msg = "ta.atr expects length, or high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        length = self._expect_int(args[3], msg)
        if self._use_incremental_ta():
            return self._atr_inc_update(args[0], args[1], args[2], length)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        return self._finalize_series(self._atr(highs, lows, closes, length))

    def _builtin_ta_kc(self, args: list[Any]) -> tuple[float, float, float]:
        """Keltner Channels (returns middle, upper, lower).

        TV: ``ta.kc(series, length, mult)``; legacy ``(high, low, close, length)``.
        """
        mult = 1.0
        use_inc = self._use_incremental_ta()
        if len(args) == TERNARY and self._is_period_like(args[1]):
            closes = self._as_series_or_raw(args[0], last_sample_ok=True)
            length = self._expect_int(args[1], "ta.kc length must be integer")
            m = args[2]
            current = getattr(m, "current", None)
            if current is not None and not isinstance(m, (list, tuple, str, bytes, int, float)):
                m = current
            if isinstance(m, (int, float)) and not isinstance(m, bool):
                mult = float(m)
            if use_inc:
                highs = self._context_source("high") or closes
                lows = self._context_source("low") or closes
            else:
                closes = self._as_series(args[0]) if not isinstance(closes, list) else closes
                highs = self._context_series("high") or closes
                lows = self._context_series("low") or closes
        elif len(args) >= QUATERNARY:
            length = self._expect_int(args[3], "ta.kc length must be integer")
            if len(args) > QUATERNARY and isinstance(args[4], (int, float)):
                mult = float(args[4])
            if use_inc:
                highs, lows, closes = args[0], args[1], args[2]
            else:
                highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
                lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
                closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        else:
            self._error("ta.kc takes (series, length, mult) or (high, low, close, length)")
            return math.nan, math.nan, math.nan

        if length < 1:
            self._error("ta.kc length must be positive")

        if use_inc:
            return self._kc_inc_update(highs, lows, closes, length, mult)

        n = min(len(highs), len(lows), len(closes)) if highs and lows and closes else 0
        if n == 0:
            return math.nan, math.nan, math.nan
        highs, lows, closes = highs[-n:], lows[-n:], closes[-n:]

        ema_vals = self._ema(closes, length)
        middle = ema_vals[-1] if ema_vals else math.nan
        atr_series = self._builtin_ta_atr([highs, lows, closes, length])
        atr_val = atr_series[-1] if isinstance(atr_series, list) and atr_series else (atr_series or 0)
        if isinstance(atr_val, list):
            atr_val = atr_val[-1] if atr_val else 0
        channel_width = (atr_val or 0) * mult
        upper = middle + channel_width if middle is not None and middle == middle else math.nan
        lower = middle - channel_width if middle is not None and middle == middle else math.nan
        return middle, upper, lower

    def _builtin_ta_kcw(self, args: list[Any]) -> float:
        """Keltner Channels Width."""
        _, upper, lower = self._builtin_ta_kc(args)
        if isinstance(upper, float) and math.isnan(upper):
            return math.nan
        if isinstance(lower, float) and math.isnan(lower):
            return math.nan
        try:
            return float(upper) - float(lower)
        except (TypeError, ValueError):
            return math.nan

    def _builtin_ta_dmi(self, args: list[Any]) -> tuple[float, float, float]:
        """Directional Movement Index.

        TradingView: ``ta.dmi(diLength, adxSmoothing) → [+DI, -DI, ADX]`` using
        chart high/low/close. Legacy 4-arg ``(high, low, close, length)`` still
        accepted (adxSmoothing defaults to diLength).
        """
        import math

        if len(args) == BINARY:
            di_len = self._expect_int(args[0], "ta.dmi diLength must be int")
            adx_smooth = self._expect_int(args[1], "ta.dmi adxSmoothing must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
        elif len(args) == QUATERNARY:
            highs = self._expect_list(args[0], "ta.dmi takes high, low, close series and length")
            lows = self._expect_list(args[1], "ta.dmi takes high, low, close series and length")
            closes = self._expect_list(args[2], "ta.dmi takes high, low, close series and length")
            di_len = self._expect_int(args[3], "ta.dmi takes high, low, close series and length")
            adx_smooth = di_len
        else:
            self._error("ta.dmi takes (diLength, adxSmoothing) or (high, low, close, length)")
            return math.nan, math.nan, math.nan

        if di_len < 1:
            self._error("ta.dmi length must be positive")
        if not (len(highs) == len(lows) == len(closes)) or not highs:
            return math.nan, math.nan, math.nan

        if self._use_incremental_ta():
            return self._dmi_inc_update(highs, lows, closes, di_len, adx_smooth)

        plus_dm: list[float] = []
        minus_dm: list[float] = []
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

        tr_series = self._tr(highs, lows, closes) if hasattr(self, "_tr") else []
        if not tr_series:
            atr_series = self._builtin_ta_atr([highs, lows, closes, di_len])
            atr_val = atr_series[-1] if isinstance(atr_series, list) and atr_series else atr_series or 1
            if isinstance(atr_val, list):
                atr_val = atr_val[-1] if atr_val else 1
            plus_di = 100 * (sum(plus_dm[-di_len:]) / di_len) / atr_val if atr_val else 0
            minus_di = 100 * (sum(minus_dm[-di_len:]) / di_len) / atr_val if atr_val else 0
            adx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) else 0
            return float(plus_di), float(minus_di), float(adx)

        # Preferred path via RMA-smoothed ADX when helpers exist
        if hasattr(self, "_adx"):
            adx = float(self._adx(highs, lows, closes, adx_smooth) or 0)
        else:
            adx = 0.0
        atr_series = self._rma(tr_series, di_len) if hasattr(self, "_rma") else [1.0]
        atr_val = atr_series[-1] if atr_series else 1.0
        plus_rma = self._rma(plus_dm, di_len) if hasattr(self, "_rma") else plus_dm
        minus_rma = self._rma(minus_dm, di_len) if hasattr(self, "_rma") else minus_dm
        pd = plus_rma[-1] if plus_rma else 0.0
        md = minus_rma[-1] if minus_rma else 0.0
        plus_di = 100 * pd / atr_val if atr_val else 0.0
        minus_di = 100 * md / atr_val if atr_val else 0.0
        if not hasattr(self, "_adx"):
            denom = plus_di + minus_di
            adx = abs(plus_di - minus_di) / denom * 100 if denom else 0.0
        return float(plus_di), float(minus_di), float(adx)

    def _builtin_ta_supertrend(self, args: list[Any]) -> tuple[float, int]:
        """Supertrend indicator.

        TradingView: ``ta.supertrend(factor, atrPeriod)`` → ``[supertrend, direction]``.
        Also accepts legacy ``(high, low, length, multiplier)``.
        """
        if len(args) == BINARY and all(isinstance(a, (int, float)) and not isinstance(a, bool) for a in args):
            factor = float(args[0])
            atr_period = self._expect_int(args[1], "ta.supertrend atrPeriod must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
        elif len(args) >= TERNARY:
            highs = self._as_series(args[0])
            lows = self._as_series(args[1])
            atr_period = self._expect_int(args[2], "ta.supertrend length must be int")
            factor = float(args[3]) if len(args) > 3 and isinstance(args[3], (int, float)) else 3.0
            closes = self._context_series("close") or highs
        else:
            self._error("ta.supertrend takes factor, atrPeriod (or high, low, length, multiplier)")
            return 0.0, 1

        if atr_period < 1:
            self._error("ta.supertrend length must be positive")

        close_s = closes if closes else highs
        if self._use_incremental_ta():
            return self._supertrend_inc_update(highs, lows, close_s, factor, atr_period)

        atr_val = self._builtin_ta_atr([highs, lows, close_s, atr_period])
        if isinstance(atr_val, list):
            atr_val = atr_val[-1] if atr_val else 0.0
        if atr_val is None or not isinstance(atr_val, (int, float)):
            atr_val = 0.0

        current_high = highs[-1] if highs and isinstance(highs[-1], (int, float)) else 0.0
        current_low = lows[-1] if lows and isinstance(lows[-1], (int, float)) else 0.0
        current_close = close_s[-1] if close_s and isinstance(close_s[-1], (int, float)) else current_high
        mid = (current_high + current_low) / 2.0

        upper = mid + factor * float(atr_val)
        lower = mid - factor * float(atr_val)
        # Simplified direction: price above mid → uptrend (-1 in TV convention for up fill)
        direction = -1 if current_close >= mid else 1
        supertrend = lower if direction < 0 else upper
        return float(supertrend), direction

    def _builtin_ta_linreg(self, args: list[Any]) -> float:
        """Linear Regression value.

        TV: ``ta.linreg(source, length, offset)`` — offset is optional (default 0).
        Length < 2 is soft-na (TV returns na rather than hard-error for short length).
        """
        if self._use_incremental_ta():
            if len(args) < BINARY:
                self._error("ta.linreg requires source and length")
            length = self._expect_int(args[1], "ta.linreg length must be int")
            # Soft-na for length < 2 (OTT scripts use length=1 default).
            if length < 2:
                return math.nan
            return self._linreg_inc_update(args[0], length)

        if len(args) == TERNARY:
            series = self._as_series(args[0])
            length = self._expect_int(args[1], "ta.linreg length must be int")
            # offset currently ignored for scalar last-value form
            _offset = args[2]
        else:
            series, length = self._expect_series(args, length=BINARY)

        # Soft-na: regression needs ≥2 points; TV yields na for length 0/1.
        if length < 2:
            return math.nan
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

        series = self._as_series(args[0])
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

    def _builtin_ta_swma(self, args: list[Any]) -> float | None:
        """Symmetric Weighted Moving Average (TV: one-arg source)."""
        if len(args) >= 1:
            if self._use_incremental_ta():
                return self._swma_inc_update(args[0])
            return self._swma(self._as_series(args[0]))
        self._error("ta.swma expects a source series")
        return None

    def _builtin_ta_swma_legacy_unused(self, args: list[Any]) -> float | None:
        """Kept only to avoid accidental name clashes; not registered."""
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
        """Maximum value over a period (alias for ta.highest).

        Also accepts a single series arg (extension methods like
        ``method max(float data) => ta.max(data)``) — returns the max of
        available history, or the scalar itself.
        """
        if len(args) == 1:
            series = self._as_series(args[0])
            valid = [v for v in series if v is not None and isinstance(v, (int, float))]
            return max(valid) if valid else None
        series, period = self._expect_series(args, length=2)
        return self._highest(series, period)

    def _builtin_ta_min(self, args: list[Any]) -> float | None:
        """Minimum value over a period (alias for ta.lowest).

        Single-arg form mirrors ``ta.max`` (full-history min / scalar).
        """
        if len(args) == 1:
            series = self._as_series(args[0])
            valid = [v for v in series if v is not None and isinstance(v, (int, float))]
            return min(valid) if valid else None
        series, period = self._expect_series(args, length=2)
        return self._lowest(series, period)

    def _builtin_ta_cum(self, args: list[Any]) -> float | None:
        """Cumulative sum. TV: ``ta.cum(source)`` — accepts series-like objects."""
        msg = "ta.cum expects a series"
        if len(args) != UNARY:
            self._error(msg)
        if self._use_incremental_ta():
            return self._cum_inc_update(args[0])
        series = self._as_series(args[0])
        if not series:
            return None
        total = 0.0
        for v in series:
            if v is None:
                continue
            try:
                total += float(v)
            except (TypeError, ValueError):
                continue
        return total

    def _builtin_ta_dev(self, args: list[Any]) -> float | None:
        """Deviation from mean (mean absolute deviation)."""
        series, period = self._expect_series(args, length=2, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._dev_inc_update(series, period)
        return self._dev(series, period)

    def _builtin_ta_median(self, args: list[Any]) -> float | None:
        """Median value over a period."""
        series, period = self._expect_series(args, length=2, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._median_inc_update(series, period)
        return self._median(series, period)

    def _builtin_ta_mode(self, args: list[Any]) -> float | None:
        """Mode (most frequent value) over a period."""
        series, period = self._expect_series(args, length=2)
        return self._mode(series, period)

    def _builtin_ta_percentrank(self, args: list[Any]) -> float | None:
        """Percentile rank of current value in period."""
        series, period = self._expect_series(args, length=2, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._percentrank_inc_update(series, period)
        return self._percentrank(series, period)

    def _builtin_ta_percentile_linear_interpolation(self, args: list[Any]) -> float | None:
        """ta.percentile_linear_interpolation(source, length, percentage)."""
        if len(args) < 3:
            self._error("ta.percentile_linear_interpolation requires series, length, percentage")
        period = self._expect_int(args[1], "length must be int")
        percentage = args[2]
        if not isinstance(percentage, (int, float)):
            self._error("percentage must be number")
        if self._use_incremental_ta():
            series = self._as_series_or_raw(args[0], last_sample_ok=True)
            return self._percentile_linear_inc_update(series, period, float(percentage))
        series = self._as_series(args[0]) if hasattr(self, "_as_series") else (
            args[0] if isinstance(args[0], list) else [args[0]]
        )
        if len(series) < period or period <= 0:
            return None
        window = [v for v in series[-period:] if v is not None]
        if not window:
            return None
        sorted_w = sorted(window)
        n = len(sorted_w)
        if n == 1:
            return float(sorted_w[0])
        rank = (float(percentage) / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return float(sorted_w[lo]) * (1 - frac) + float(sorted_w[hi]) * frac

    def _builtin_ta_percentile_nearest_rank(self, args: list[Any]) -> float | None:
        """ta.percentile_nearest_rank(source, length, percentage)."""
        if len(args) < 3:
            self._error("ta.percentile_nearest_rank requires series, length, percentage")
        period = self._expect_int(args[1], "length must be int")
        percentage = args[2]
        if not isinstance(percentage, (int, float)):
            self._error("percentage must be number")
        if self._use_incremental_ta():
            series = self._as_series_or_raw(args[0], last_sample_ok=True)
            return self._percentile_nearest_rank_inc_update(series, period, float(percentage))
        series = self._as_series(args[0]) if hasattr(self, "_as_series") else (
            args[0] if isinstance(args[0], list) else [args[0]]
        )
        if len(series) < period or period <= 0:
            return None
        window = [v for v in series[-period:] if v is not None]
        if not window:
            return None
        sorted_w = sorted(window)
        n = len(sorted_w)
        # Nearest rank: ceil(p/100 * n), 1-indexed, clamped
        rank = max(1, int((float(percentage) / 100.0) * n + 0.999999))
        rank = min(rank, n)
        return float(sorted_w[rank - 1])

    def _builtin_ta_variance(self, args: list[Any]) -> float | None:
        """Variance over a period."""
        series, period = self._expect_series(args, length=2, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._variance_inc_update(series, period)
        return self._variance(series, period)

    def _builtin_ta_barssince(self, args: list[Any]) -> int | None:
        """Bars since condition was last true."""
        if len(args) != 1:
            msg = "ta.barssince() takes exactly one argument"
            self._error(msg)
        condition = args[0]
        if self._use_incremental_ta():
            return self._barssince_inc_update(condition)
        # If condition is a list (series), check from the end backwards
        if isinstance(condition, list):
            for i in range(len(condition) - 1, -1, -1):
                is_true = condition[i] is True or (condition[i] is not None and condition[i] is not False)
                if is_true:
                    return len(condition) - 1 - i
            return len(condition) - 1
        # If condition is boolean without bar-mode state, return 0 if true, 1 if false
        is_true = condition is True or (condition is not None and condition is not False)
        if is_true:
            return 0
        return 1

    @staticmethod
    def _pivot_scalar(value: Any) -> float | None:
        """Coerce a pivot sample to float, unwrapping PineSeries-like wrappers."""
        if value is None:
            return None
        t = type(value)
        if t is float:
            return value
        if t is int and t is not bool:
            return float(value)
        # PineSeries / _SeriesResult: use .current (may itself be na)
        current = getattr(value, "current", None)
        if current is not None and t.__name__ in {"PineSeries", "_SeriesResult"}:
            value = current
        elif current is not None and hasattr(value, "history"):
            value = current
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _pivot_source_series(self, source: Any) -> list[Any]:
        """Materialize pivot source as chronological list (list / PineSeries / scalar)."""
        if isinstance(source, list):
            return self._cap_series_list(source)
        # PineSeries and other history wrappers → chronological via _as_series
        return self._as_series(source)

    def _builtin_ta_pivothigh(self, args: list[Any]) -> float | None:
        """Find the highest point (pivot high) in a window.

        TV: ``ta.pivothigh(leftbars, rightbars)`` (source=high) or
        ``ta.pivothigh(source, leftbars, rightbars)``.

        Source may be a list (``current_series``), a ``PineSeries`` from the
        runtime host, or a bare scalar; always materialize before float().
        """
        if len(args) == BINARY and self._is_period_like(args[0]) and self._is_period_like(args[1]):
            source = self._context_series("high")
            left_bars = self._expect_int(args[0], "leftbars must be integer")
            right_bars = self._expect_int(args[1], "rightbars must be integer")
        elif len(args) >= 3:
            source = self._pivot_source_series(args[0])
            left_bars = self._expect_int(args[1], "leftbars must be integer")
            right_bars = self._expect_int(args[2], "rightbars must be integer")
        else:
            msg = "ta.pivothigh() requires 2 or 3 arguments: [source,] leftbars, rightbars"
            self._error(msg)
            return None

        if not isinstance(source, list):
            source = self._pivot_source_series(source)

        if self._use_incremental_ta():
            return self._pivothigh_inc_update(source, left_bars, right_bars)

        if len(source) <= left_bars + right_bars:
            return None

        # Get current value (last in chronological series)
        current_idx = len(source) - 1
        current = self._pivot_scalar(source[current_idx])
        if current is None:
            return None

        # Check left bars (strict local max)
        for i in range(1, left_bars + 1):
            if current_idx - i < 0:
                return None
            left_val = self._pivot_scalar(source[current_idx - i])
            if left_val is not None and left_val >= current:
                return None

        # Check right bars - would need future bars
        # For now, only check left bars
        return current

    def _builtin_ta_pivotlow(self, args: list[Any]) -> float | None:
        """Find the lowest point (pivot low) in a window.

        TV: ``ta.pivotlow(leftbars, rightbars)`` (source=low) or
        ``ta.pivotlow(source, leftbars, rightbars)``.

        Source may be a list, ``PineSeries``, or scalar — see pivothigh.
        """
        if len(args) == BINARY and self._is_period_like(args[0]) and self._is_period_like(args[1]):
            source = self._context_series("low")
            left_bars = self._expect_int(args[0], "leftbars must be integer")
            right_bars = self._expect_int(args[1], "rightbars must be integer")
        elif len(args) >= 3:
            source = self._pivot_source_series(args[0])
            left_bars = self._expect_int(args[1], "leftbars must be integer")
            right_bars = self._expect_int(args[2], "rightbars must be integer")
        else:
            msg = "ta.pivotlow() requires 2 or 3 arguments: [source,] leftbars, rightbars"
            self._error(msg)
            return None

        if not isinstance(source, list):
            source = self._pivot_source_series(source)

        if self._use_incremental_ta():
            return self._pivotlow_inc_update(source, left_bars, right_bars)

        if len(source) <= left_bars + right_bars:
            return None

        current_idx = len(source) - 1
        current = self._pivot_scalar(source[current_idx])
        if current is None:
            return None

        for i in range(1, left_bars + 1):
            if current_idx - i < 0:
                return None
            left_val = self._pivot_scalar(source[current_idx - i])
            if left_val is not None and left_val <= current:
                return None

        # Check right bars - would need future bars
        # For now, only check left bars
        return current

    def _builtin_ta_pivot_point_levels(self, args: list[Any]) -> Any:
        """Calculate pivot point levels.

        TV: ``ta.pivot_point_levels(type, anchor, developing?)`` → array of floats
        using chart high/low/close. Legacy: ``(high, low, close, is_traditional)``.
        """
        # TV form: type is a string ("Traditional", "Fibonacci", …)
        if args and isinstance(args[0], str):
            ptype = args[0]
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if not highs or not lows or not closes:
                return []
            high = float(highs[-1]) if highs[-1] is not None else None
            low = float(lows[-1]) if lows[-1] is not None else None
            close = float(closes[-1]) if closes[-1] is not None else None
            if high is None or low is None or close is None:
                return []
            levels = self._pivot_levels_for_type(ptype, high, low, close)
            return levels

        if len(args) < 3:
            msg = "ta.pivot_point_levels() requires type+anchor or high, low, close"
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

    def _pivot_levels_for_type(
        self,
        ptype: str,
        high: float,
        low: float,
        close: float,
    ) -> list[float]:
        """Return pivot levels as a flat list (TV array order: P, R1, S1, R2, S2, R3, S3)."""
        pivot = (high + low + close) / 3.0
        diff = high - low
        kind = (ptype or "Traditional").strip().lower()
        if kind in {"fibonacci", "fib"}:
            r1 = pivot + 0.382 * diff
            s1 = pivot - 0.382 * diff
            r2 = pivot + 0.618 * diff
            s2 = pivot - 0.618 * diff
            r3 = pivot + diff
            s3 = pivot - diff
        elif kind in {"woodie", "woodies"}:
            pivot = (high + low + 2 * close) / 4.0
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + diff
            s2 = pivot - diff
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        elif kind in {"classic"}:
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + diff
            s2 = pivot - diff
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        elif kind in {"dm"}:
            # DeMark (simplified without open series)
            x = high + low + 2 * close
            pivot = x / 4.0
            r1 = x / 2.0 - low
            s1 = x / 2.0 - high
            return [pivot, r1, s1]
        elif kind in {"camarilla"}:
            r1 = close + diff * 1.1 / 12.0
            s1 = close - diff * 1.1 / 12.0
            r2 = close + diff * 1.1 / 6.0
            s2 = close - diff * 1.1 / 6.0
            r3 = close + diff * 1.1 / 4.0
            s3 = close - diff * 1.1 / 4.0
            r4 = close + diff * 1.1 / 2.0
            s4 = close - diff * 1.1 / 2.0
            return [pivot, r1, s1, r2, s2, r3, s3, r4, s4]
        else:
            # Traditional
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + diff
            s2 = pivot - diff
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        return [pivot, r1, s1, r2, s2, r3, s3]

    # Helper implementations

    def _range(self, series: list[float], period: int) -> float | None:
        """Range = highest - lowest over a period."""
        highest = self._highest(series, period)
        lowest = self._lowest(series, period)
        if highest is None or lowest is None:
            return None
        return highest - lowest

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
