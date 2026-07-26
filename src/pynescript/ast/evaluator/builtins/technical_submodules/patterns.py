# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Pattern Recognition Technical Indicators."""

from __future__ import annotations

from typing import Any

from .core import TechnicalHelpers


class PatternIndicators(TechnicalHelpers):
    """Pattern-based technical indicators: Engulfing, Hammer, Gap, SAR, etc."""

    # -- Public API (builtin_ta_ prefix) ------------------------------------

    def _builtin_ta_sar(self, args: list[Any]) -> list[float]:
        """Parabolic SAR (Stop and Reverse).

        ta.sar(high, low, start, increment, max)
        Trailing stop indicator.
        Returns SAR series.
        """
        msg = "ta.sar expects high, low, start, increment, max"
        if len(args) != 5:  # QUINARY
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        start = self._expect_number(args[2], msg)
        increment = self._expect_number(args[3], msg)
        maximum = self._expect_number(args[4], msg)
        return self._sar(highs, lows, start, increment, maximum)

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

        return self._engulfing(opens, closes)

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

        return self._hammer(opens, highs, lows, closes)

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

        return self._gap_detector(highs, lows, prev_close)

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

        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])

        if not highs or not lows or len(highs) < period * 2 + 1:
            return {"is_high_fractal": False, "is_low_fractal": False}

        # Check if current bar is a high fractal
        current_idx = len(highs) - 1
        is_high_fractal = highs[current_idx] == max(
            highs[current_idx - period : current_idx + period + 1]
        )

        # Check if current bar is a low fractal
        is_low_fractal = lows[current_idx] == min(
            lows[current_idx - period : current_idx + period + 1]
        )

        return {"is_high_fractal": is_high_fractal, "is_low_fractal": is_low_fractal}

    def _builtin_ta_double_top_bottom(self, args: list[Any]) -> dict[str, Any]:
        """Double Top/Bottom Pattern - Identifies classic reversal patterns.

        ta.double_top_bottom(high, low, period)
        Returns: {pattern_type, strength, breakout_level}.
        """
        if len(args) < 3:
            msg = "ta.double_top_bottom() requires 3 arguments"
            self._error(msg)

        high_list = args[0] if isinstance(args[0], list) else [args[0]]
        low_list = args[1] if isinstance(args[1], list) else [args[1]]
        period = self._expect_int(args[2], "period must be integer")

        if len(high_list) < period or len(low_list) < period:
            return {"pattern_type": "none", "strength": 0.0, "breakout_level": 0.0}

        recent_high = [h for h in high_list[-period:] if isinstance(h, (int, float))]
        recent_low = [low_val for low_val in low_list[-period:] if isinstance(low_val, (int, float))]

        if len(recent_high) < 3:
            return {"pattern_type": "none", "strength": 0.0, "breakout_level": 0.0}

        peaks = [recent_high[0]]
        for i in range(1, len(recent_high) - 1):
            if (
                recent_high[i] > recent_high[i - 1]
                and recent_high[i] > recent_high[i + 1]
            ):
                peaks.append(recent_high[i])

        if len(peaks) >= 2:
            peak_diff = abs(peaks[-1] - peaks[-2])
            avg_peak = (peaks[-1] + peaks[-2]) / 2.0
            strength = (
                1.0 - min(1.0, peak_diff / avg_peak) if avg_peak > 0 else 0.0
            )
            breakout_level = min(recent_low) - (avg_peak * 0.1)
            return {
                "pattern_type": "double_top",
                "strength": strength,
                "breakout_level": breakout_level,
            }

        return {"pattern_type": "none", "strength": 0.0, "breakout_level": 0.0}

    # -- Implementation helpers (private _method prefix) --------------------

    def _sar(
        self,
        highs: list[float],
        lows: list[float],
        start: float,
        increment: float,
        maximum: float,
    ) -> list[float]:
        """Calculate Parabolic SAR."""
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
        """Calculate Parabolic SAR with trend information."""
        if not highs or not lows:
            return [], 0
        # Skip leading na (empty series / warm-up)
        start_i = 0
        n = min(len(highs), len(lows))
        while start_i < n and (highs[start_i] is None or lows[start_i] is None):
            start_i += 1
        if start_i >= n:
            return [None] * n, 0
        sar_values: list[float | None] = [None] * start_i
        try:
            sar0 = float(lows[start_i])
            ep = float(highs[start_i])
        except (TypeError, ValueError):
            return [None] * n, 0
        sar_values.append(sar0)
        trend = 1
        af = start
        for idx in range(start_i + 1, n):
            previous = sar_values[-1]
            hi, lo = highs[idx], lows[idx]
            if previous is None or hi is None or lo is None or ep is None:
                sar_values.append(previous)
                continue
            try:
                hi_f, lo_f = float(hi), float(lo)
            except (TypeError, ValueError):
                sar_values.append(previous)
                continue
            if trend == 1:
                sar = previous + af * (ep - previous)
                if hi_f > ep:
                    ep = hi_f
                    af = min(af + increment, maximum)
                if sar > lo_f:
                    trend = -1
                    sar = ep
                    ep = lo_f
                    af = start
            else:
                sar = previous - af * (previous - ep)
                if lo_f < ep:
                    ep = lo_f
                    af = min(af + increment, maximum)
                if sar < hi_f:
                    trend = 1
                    sar = ep
                    ep = hi_f
                    af = start
            sar_values.append(sar)
        return sar_values, trend

    def _engulfing(
        self,
        opens: list[Any],
        closes: list[Any],
    ) -> dict[str, bool | float]:
        """Detect engulfing patterns."""
        current_open = opens[-1]
        current_close = closes[-1]

        prev_open = opens[-2]
        prev_close = closes[-2]

        # Bullish engulfing: current candle engulfs previous and is green
        is_bullish = (
            current_open < prev_close
            and current_close > prev_open
            and current_close > current_open
        )

        # Bearish engulfing: current candle engulfs previous and is red
        is_bearish = (
            current_open > prev_close
            and current_close < prev_open
            and current_close < current_open
        )

        # Pattern strength (0-1) based on how much body engulfed
        if is_bullish:
            engulf_amount = max(
                0,
                min(
                    1,
                    (current_close - prev_open)
                    / abs(prev_open - prev_close + 0.0001),
                ),
            )
        elif is_bearish:
            engulf_amount = max(
                0,
                min(
                    1,
                    (prev_open - current_close)
                    / abs(prev_close - prev_open + 0.0001),
                ),
            )
        else:
            engulf_amount = 0.0

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "pattern_strength": engulf_amount,
        }

    def _hammer(
        self,
        opens: list[Any],
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
    ) -> dict[str, bool | float]:
        """Detect hammer and doji patterns."""
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
            body_size > 0 and lower_wick > body_size * 2 and upper_wick < body_size
        )

        # Pattern strength
        if is_doji:
            strength = 1.0 - (body_size / (total_range + 0.0001))
        elif is_hammer:
            strength = min(1.0, lower_wick / (total_range + 0.0001))
        else:
            strength = 0.0

        return {
            "is_hammer": is_hammer,
            "is_doji": is_doji,
            "pattern_strength": strength,
        }

    def _gap_detector(
        self,
        highs: list[Any],
        lows: list[Any],
        prev_close: float,
    ) -> dict[str, float | int]:
        """Detect price gaps."""
        current_high = highs[-1]
        current_low = lows[-1]

        # Upside gap: current low > prev close
        upside_gap = max(0, current_low - prev_close)

        # Downside gap: current high < prev close
        downside_gap = max(0, prev_close - current_high)

        if upside_gap > downside_gap:
            gap_size = upside_gap
            gap_type = 1  # Upside
            gap_percent = (
                (upside_gap / prev_close * 100) if prev_close != 0 else 0.0
            )
        elif downside_gap > 0:
            gap_size = downside_gap
            gap_type = -1  # Downside
            gap_percent = (
                (downside_gap / prev_close * 100) if prev_close != 0 else 0.0
            )
        else:
            gap_size = 0.0
            gap_type = 0  # No gap
            gap_percent = 0.0

        return {
            "gap_size": gap_size,
            "gap_type": gap_type,
            "gap_percent": gap_percent,
        }
