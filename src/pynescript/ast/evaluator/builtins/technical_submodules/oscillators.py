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

"""Oscillator ``ta.*`` family (RSI, Stoch, MACD, CCI, ROC, WPR, TSI, …).

Handlers are composed into
:class:`~pynescript.ast.evaluator.builtins.technical.TechnicalAnalysisMixin`.
"""

from __future__ import annotations

import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import QUINARY
from .core import TERNARY
from .core import UNARY
from .core import TechnicalHelpers


class OscillatorIndicators(TechnicalHelpers):
    """Momentum oscillators: RSI, Stochastic, MACD, CCI, ROC, Williams %R, TSI."""

    def _builtin_ta_rsi(self, args: list[Any]) -> float | None:
        """Relative Strength Index."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._rsi_inc_update(series, period)
        return self._rsi(series, period)

    def _builtin_ta_stoch(self, args: list[Any]) -> Any:
        """Stochastic %K.

        Forms:
        - ``ta.stoch(length)`` — source=close, high/low from context
        - ``ta.stoch(source, high, low, length)`` → float %K
        - Legacy: ``(high, low, close, length, smooth)``
        """
        if len(args) == UNARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.stoch length must be an integer")
            source = self._context_series("close")
            highs = self._context_series("high")
            lows = self._context_series("low")
            return self._stoch_k(source, highs, lows, length)
        # TV form: source, high, low, length
        if len(args) == QUATERNARY:
            length = self._expect_int(args[3], "ta.stoch length must be an integer")
            # Inc %K only needs last samples; full path needs chrono windows.
            source = self._as_series_or_raw(args[0], last_sample_ok=True)
            highs = self._as_series_or_raw(args[1], last_sample_ok=True)
            lows = self._as_series_or_raw(args[2], last_sample_ok=True)
            return self._stoch_k(source, highs, lows, length)
        # Two-arg community form sometimes used as (kLength, dPeriod) — return %K only
        if len(args) == BINARY and self._is_period_like(args[0]) and self._is_period_like(args[1]):
            length = self._expect_int(args[0], "ta.stoch length must be an integer")
            source = self._context_series("close")
            highs = self._context_series("high")
            lows = self._context_series("low")
            return self._stoch_k(source, highs, lows, length)
        msg = "ta.stoch expects source, high, low, length (or high, low, close, length, smooth)"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        smooth_k = self._expect_int(args[4], msg)
        return self._stoch(highs, lows, closes, length, smooth_k)

    def _stoch_k(
        self,
        source: list[Any],
        highs: list[Any],
        lows: list[Any],
        length: int,
    ) -> float | None:
        """Compute current Stochastic %K for the last bar.

        Important: do **not** early-return on ``not source`` when *source* is a
        scalar ``None`` / ``0.0``. Incremental TA assigns call-site slots via
        ``_ta_next_slot``; skipping that on warm-up bars (``rsi`` still ``na``)
        shifts later ``ema``/``sma`` slots and corrupts their seed state.
        Empty **lists** are still a hard no-op without consuming a slot.
        """
        if length <= 0:
            return None
        if isinstance(source, (list, tuple)) and len(source) == 0:
            return None
        if self._use_incremental_ta():
            return self._stoch_k_inc_update(source, highs, lows, length)
        n = len(source)
        start = max(0, n - length)
        window_h = [highs[i] for i in range(start, min(n, len(highs))) if highs[i] is not None]
        window_l = [lows[i] for i in range(start, min(n, len(lows))) if lows[i] is not None]
        c = source[-1]
        if c is None or not window_h or not window_l:
            return None
        hh = max(window_h)
        ll = min(window_l)
        if hh == ll:
            return 50.0
        try:
            return 100.0 * (float(c) - float(ll)) / (float(hh) - float(ll))
        except (TypeError, ValueError):
            return None

    def _builtin_ta_macd(self, args: list[Any]) -> tuple[float, float, float]:
        """MACD (Moving Average Convergence Divergence).

        TradingView: ``ta.macd(source, fastlen, slowlen, siglen)`` →
        ``[macdLine, signalLine, histLine]``.

        Accepts:
        - Full form with series + three lengths (defaults 12/26/9 if omitted).
        - Series may be a list, PineSeries, or scalar wrapper (bar-mode input).
        - Extra / unknown kwargs are ignored by the call site (ta.* path).
        """
        msg = "ta.macd expects series and three lengths"
        if not args:
            self._error(msg)
        # Defaults match TradingView when lengths are omitted
        fast = self._expect_int(args[1], msg) if len(args) > 1 else 12
        slow = self._expect_int(args[2], msg) if len(args) > 2 else 26
        signal = self._expect_int(args[3], msg) if len(args) > 3 else 9
        series = self._as_series_or_raw(args[0], last_sample_ok=True)
        if self._use_incremental_ta():
            return self._macd_inc_update(series, fast, slow, signal)
        return self._macd(series, fast, slow, signal)

    def _builtin_ta_cci(self, args: list[Any]) -> float | None:
        """Commodity Channel Index.

        Forms:
        - ``ta.cci(length)`` — typical price (hlc3) from context
        - ``ta.cci(source, length)``
        - legacy ``(high, low, close, length)``
        """
        if len(args) == UNARY and self._is_period_like(args[0]):
            period = self._expect_int(args[0], "ta.cci length must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if highs and lows and closes:
                if self._use_incremental_ta():
                    return self._cci_inc_update(highs, lows, closes, period)
                return self._cci(highs, lows, closes, period)
            series = self._context_series("hlc3") or closes
            if self._use_incremental_ta():
                return self._cci_inc_update(series, series, series, period)
            return self._cci(series, series, series, period)
        if len(args) == BINARY:
            series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
            # Approximate CCI from a single source series (typical price)
            if self._use_incremental_ta():
                return self._cci_inc_update(series, series, series, period)
            return self._cci(series, series, series, period)
        msg = "ta.cci expects source, length (or high, low, close, length)"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        if self._use_incremental_ta():
            return self._cci_inc_update(highs, lows, closes, length)
        return self._cci(highs, lows, closes, length)

    def _builtin_ta_roc(self, args: list[Any]) -> float:
        """Rate of Change."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._roc_inc_update(series, period)
        return self._roc(series, period)

    def _builtin_ta_wpr(self, args: list[Any]) -> float | None:
        """Williams %R. TV: ``ta.wpr(length)`` or legacy 4-arg form."""
        if len(args) == UNARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.wpr length must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if self._use_incremental_ta():
                return self._wpr_inc_update(highs, lows, closes, length)
            return self._wpr(highs, lows, closes, length)
        msg = "ta.wpr expects length (or high, low, close, length)"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        if self._use_incremental_ta():
            return self._wpr_inc_update(highs, lows, closes, length)
        return self._wpr(highs, lows, closes, length)

    def _builtin_ta_ao(self, args: list[Any]) -> float | None:
        """Awesome Oscillator: ``sma(hl2, 5) - sma(hl2, 34)`` (TV ``ta.ao``).

        Optional args override fast/slow periods (default 5 / 34).
        """
        fast = 5
        slow = 34
        if len(args) >= 1 and self._is_period_like(args[0]):
            fast = self._expect_int(args[0], "ta.ao fast must be int")
        if len(args) >= 2 and self._is_period_like(args[1]):
            slow = self._expect_int(args[1], "ta.ao slow must be int")
        hl2 = self._context_series("hl2")
        if not hl2:
            highs = self._context_series("high")
            lows = self._context_series("low")
            n = min(len(highs), len(lows)) if highs and lows else 0
            hl2 = [(float(highs[i]) + float(lows[i])) / 2.0 for i in range(n)] if n else []
        if len(hl2) < slow or slow <= 0 or fast <= 0:
            return None
        if self._use_incremental_ta():
            # Two independent SMA call sites (separate slots)
            fast_v = self._sma_inc_update(hl2, fast)
            slow_v = self._sma_inc_update(hl2, slow)
        else:
            fast_v = self._sma(hl2, fast)
            slow_v = self._sma(hl2, slow)
        if fast_v is None or slow_v is None:
            return None
        try:
            return float(fast_v) - float(slow_v)
        except (TypeError, ValueError):
            return None

    def _builtin_ta_aroon(self, args: list[Any]) -> tuple[float, float] | None:
        """Aroon oscillator pair: ``[aroonDown, aroonUp]`` (TV ``ta.aroon(length)``).

        ``aroonUp = 100 * (length - bars_since_hh) / length``
        ``aroonDown = 100 * (length - bars_since_ll) / length``
        """
        length = 14
        if len(args) >= 1 and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.aroon length must be int")
        if length <= 0:
            return None
        highs = self._context_series("high")
        lows = self._context_series("low")
        # Need length+1 bars of history for classic Aroon (window of length)
        window = length + 1
        if len(highs) < window or len(lows) < window:
            return None
        h_win = highs[-window:]
        l_win = lows[-window:]
        # Index of highest high / lowest low within window (0 = oldest)
        try:
            hh_i = max(range(window), key=lambda i: float(h_win[i]))
            ll_i = min(range(window), key=lambda i: float(l_win[i]))
        except (TypeError, ValueError):
            return None
        # bars since = distance from end of window
        bars_since_hh = (window - 1) - hh_i
        bars_since_ll = (window - 1) - ll_i
        aroon_up = 100.0 * (length - bars_since_hh) / length
        aroon_down = 100.0 * (length - bars_since_ll) / length
        return (float(aroon_down), float(aroon_up))

    def _builtin_ta_tsi(self, args: list[Any]) -> float | None:
        """True Strength Index.

        Forms:
        - ``ta.tsi(short, long)`` — source defaults to close
        - ``ta.tsi(source, short, long)`` — TV order (short then long)
        - Also accepts legacy ``(source, long, short)`` when 3 period-like after series
        """
        msg = "ta.tsi expects series and two lengths"
        if len(args) == BINARY and self._is_period_like(args[0]) and self._is_period_like(args[1]):
            short_period = self._expect_int(args[0], msg)
            long_period = self._expect_int(args[1], msg)
            if self._use_incremental_ta():
                return self._tsi_inc_update(
                    self._context_source("close"), long_period, short_period
                )
            series = self._context_series("close")
            return self._tsi(series, long_period, short_period)
        if len(args) != TERNARY:
            self._error(msg)
        # TV docs: ta.tsi(source, short_length, long_length)
        short_period = self._expect_int(args[1], msg)
        long_period = self._expect_int(args[2], msg)
        series = self._as_series_or_raw(args[0], last_sample_ok=True)
        if self._use_incremental_ta():
            return self._tsi_inc_update(series, long_period, short_period)
        return self._tsi(series, long_period, short_period)

    def _builtin_ta_valuewhen(self, args: list[Any]) -> Any:
        """Get value when condition was true. TV: ``ta.valuewhen(cond, source, occurrence=0)``."""
        msg = "ta.valuewhen expects condition, source, and optional occurrence"
        if len(args) not in {BINARY, TERNARY}:
            self._error(msg)
        occurrence = self._expect_int(args[2], msg) if len(args) == TERNARY else 0
        if self._use_incremental_ta():
            # Prefer last-sample / scalar path; avoid full ``_as_series`` when possible.
            return self._valuewhen_inc_update(args[0], args[1], occurrence)
        condition = self._as_series(args[0])
        source = self._as_series(args[1])
        return self._valuewhen(condition, source, occurrence)

    def _builtin_ta_rsi_oversold_overbought(self, args: list[Any]) -> dict:
        """RSI Oversold/Overbought Levels - Custom RSI threshold detection.

        ta.rsi_oversold_overbought(rsi_series, oversold_level, overbought_level)
        Returns boolean flags for oversold/overbought conditions.
        """
        if len(args) < TERNARY:
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

    def _builtin_ta_rsi_divergence(self, args: list[Any]) -> list[float | None]:
        """RSI Divergence Detector."""
        if len(args) < BINARY:
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

            if len(rsi_values) < BINARY:
                divergence_values.append(0.0)
                continue

            rsi_min = min(rsi_values)
            rsi_max = max(rsi_values)
            rsi_range = rsi_max - rsi_min

            if rsi_range > 0:
                divergence = (rsi_series[i] - rsi_min) / rsi_range * BINARY - 1
            else:
                divergence = 0.0

            divergence_values.append(divergence)

        return divergence_values

    def _builtin_ta_macd_signal(self, args: list[Any]) -> float | None:
        """MACD Signal Strength."""
        if len(args) < BINARY:
            msg = "ta.macd_signal() requires 2 arguments: macd_line, signal_line"
            self._error(msg)

        macd_line = args[0]
        signal_line = args[1]

        if macd_line is None or signal_line is None:
            return None

        strength = float(macd_line) - float(signal_line)
        return strength

    def _builtin_ta_stoch_smooth(self, args: list[Any]) -> list[float | None]:
        """Smoothed Stochastic Oscillator."""
        senary = 6
        if len(args) < senary:
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

    def _builtin_ta_stochrsi(self, args: list[Any]) -> dict[str, float | None]:
        """Stochastic RSI.

        ta.stochrsi(rsi_length, stoch_length)
        Returns dict with stochrsi value and signal.
        """
        if len(args) < BINARY:
            msg = "ta.stochrsi() requires 2 arguments: rsi_length, stoch_length"
            self._error(msg)

        rsi_length = self._expect_int(args[0], "rsi_length must be integer")
        stoch_length = self._expect_int(args[1], "stoch_length must be integer")

        if self._use_incremental_ta():
            closes = self._context_source("close")
            return self._stochrsi_inc_update(closes, rsi_length, stoch_length)

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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
        if len(args) < UNARY:
            msg = "ta.dpo() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < 1:
            msg = "DPO length must be >= 1"
            self._error(msg)

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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
        if len(args) < QUATERNARY:
            msg = "ta.kst() requires 4 arguments: length1, length2, length3, length4"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")
        length4 = self._expect_int(args[3], "length4 must be integer")

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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
        if len(args) < TERNARY:
            msg = "ta.uo() requires 3 arguments: length1, length2, length3"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])

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

    # Helper implementations

    def _rsi(self, series: list[float], period: int) -> float | None:
        """RSI calculation."""
        if len(series) < period + 1:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for idx in range(1, len(series)):
            prev = series[idx - 1]
            curr = series[idx]
            if prev is None or curr is None:
                gains.append(0)
                losses.append(0)
                continue
            change = curr - prev
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

    def _stoch(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
        smooth_k: int,
    ) -> tuple[float, float]:
        """Stochastic calculation."""
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

    def _macd(
        self,
        series: list[float],
        fast: int,
        slow: int,
        signal: int,
    ) -> tuple[float, float, float]:
        """MACD calculation."""
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

    def _cci(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        """CCI calculation."""
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

    def _roc(self, series: list[float], period: int) -> float | None:
        """Rate of Change: ``100 * (src - src[period]) / src[period]`` (TV ``ta.roc``).

        Returns ``None`` (``na``) when history is shorter than ``period`` bars of
        lookback, baseline is missing/zero, or the current value is missing —
        matching compile ``numba_roc`` and TradingView.
        """
        if period <= 0 or len(series) <= period:
            return None
        previous_index = len(series) - period - 1
        if previous_index < 0:
            return None
        baseline = series[previous_index]
        current = series[-1]
        if baseline in {None, 0} or current is None:
            return None
        try:
            b = float(baseline)
            c = float(current)
        except (TypeError, ValueError):
            return None
        if b == 0.0:
            return None
        return 100.0 * (c - b) / b

    def _wpr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        """Williams %R calculation."""
        if len(closes) < period or period <= 0:
            return 0.0
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        if highest_high == lowest_low:
            return 0.0
        return -100 * (highest_high - closes[-1]) / (highest_high - lowest_low)

    def _tsi(
        self,
        series: list[float],
        long_period: int,
        short_period: int,
    ) -> float | None:
        """True Strength Index calculation."""
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
        """Valuewhen calculation."""
        indices = [index for index, flag in enumerate(condition) if flag]
        if not indices or occurrence >= len(indices):
            return None
        return source[indices[-(occurrence + 1)]]


# TV parameter names for kwargs → positional merge in BuiltinDispatchMixin
OscillatorIndicators._builtin_ta_macd._KWARG_ORDER = [  # type: ignore[attr-defined]
    "source",
    "fastlen",
    "slowlen",
    "siglen",
]
