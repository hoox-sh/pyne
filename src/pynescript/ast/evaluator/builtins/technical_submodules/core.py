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

"""Core technical analysis helpers and validation utilities."""

from __future__ import annotations

import math
import os
import statistics

from collections import deque
from typing import Any


# Constants
UNARY = 1
BINARY = 2
TERNARY = 3
QUATERNARY = 4
QUINARY = 5

MIN_SERIES_LENGTH = 2


class TechnicalHelpers:
    """Shared technical analysis helpers and validation methods."""

    current_series: dict[str, list[Any]]

    def _error(self, message: str) -> Any:
        """Raise a runtime error.

        This method should be overridden by the host class (Evaluator).
        """
        msg = "Must be implemented by host class"
        raise NotImplementedError(msg)

    _SERIES_MAX = 256

    def _bar_mode(self) -> bool:
        """True when evaluating bar-by-bar (Runtime / CustomEvaluator).

        Unit tests pass explicit list histories and expect full-series
        returns; bar mode returns the current (last) scalar so Pine
        expressions like ``ta.ema(close,12) - ta.ema(close,26)`` stay
        numeric per bar without relying only on plot unwrap.
        """
        return bool(getattr(self, "_pine_bar_mode", False))

    def _use_incremental_ta(self) -> bool:
        """Use O(1)/O(period) call-site TA state in bar mode.

        Enabled when ``_pine_bar_mode`` and ``_pine_ta_incremental`` (default
        True in Runtime hosts). Disable with env ``PYNE_TA_INCREMENTAL=0`` or
        ``evaluator._pine_ta_incremental = False``.

        Resolved once per evaluator instance (hot path is called many times/bar).
        """
        cached = getattr(self, "_pine_ta_inc_cached", None)
        if cached is not None:
            return cached
        if not self._bar_mode():
            self._pine_ta_inc_cached = False  # type: ignore[attr-defined]
            return False
        env = os.environ.get("PYNE_TA_INCREMENTAL", "1").strip().lower()
        if env in {"0", "false", "no", "off"}:
            self._pine_ta_inc_cached = False  # type: ignore[attr-defined]
            return False
        result = bool(getattr(self, "_pine_ta_incremental", True))
        self._pine_ta_inc_cached = result  # type: ignore[attr-defined]
        return result

    def _ta_next_slot(self) -> int:
        """Per-bar call-site index (reset by Runtime each bar, like crossover)."""
        i = int(getattr(self, "_ta_call_i", 0) or 0)
        self._ta_call_i = i + 1  # type: ignore[attr-defined]
        return i

    def _ta_state_bucket(self) -> dict[tuple[Any, ...], dict[str, Any]]:
        state = getattr(self, "_ta_inc_state", None)
        if state is None:
            state = {}
            self._ta_inc_state = state  # type: ignore[attr-defined]
        return state

    @staticmethod
    def _series_last(series: list[Any]) -> Any:
        """Current-bar source sample (bar mode feeds one update per call)."""
        if not series:
            return None
        return series[-1]

    def _sma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental SMA matching full ``_sma`` NA-window rules (last value).

        One sample per call-site per bar (``series[-1]``). Does not depend on
        full series length — safe with ``_SERIES_MAX`` truncation.

        Maintains a running sum/count of non-None samples for O(1) updates.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("sma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "count": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        if len(window) == period:
            old = window.popleft()
            if old is not None:
                st["sum"] -= float(old)
                st["count"] -= 1
        window.append(x)
        if x is not None:
            try:
                st["sum"] += float(x)
                st["count"] += 1
            except (TypeError, ValueError):
                # Treat non-numeric as na: replace with None in window
                window[-1] = None
        if len(window) < period or st["count"] <= 0:
            st["value"] = None
        else:
            st["value"] = st["sum"] / st["count"]
        return st.get("value")

    def _ema_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental EMA matching full ``_ema`` seed/carry rules (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("ema", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"ema": None, "seeded": False}
            bucket[key] = st
        x = self._series_last(series)
        alpha = 2.0 / (period + 1)
        if not st["seeded"]:
            if x is None:
                return None
            st["ema"] = float(x)
            st["seeded"] = True
            return st["ema"]
        if x is None:
            return st.get("ema")
        prev = st["ema"]
        if prev is None:
            st["ema"] = float(x)
        else:
            st["ema"] = alpha * float(x) + (1.0 - alpha) * float(prev)
        return st.get("ema")

    def _rma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental RMA (Wilder) matching full ``_rma`` seed rules (last value).

        Seed = mean of first ``period`` non-nan samples after the first valid
        bar; then ``alpha * x + (1-alpha) * rma`` with alpha=1/period.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("rma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "seed_buf": [],
                "rma": None,
                "seeded": False,
                "started": False,
                "value": None,
            }
            bucket[key] = st
        raw = self._series_last(series)
        if raw is None:
            x = math.nan
        else:
            try:
                x = float(raw)
            except (TypeError, ValueError):
                x = math.nan
        alpha = 1.0 / period
        if not st["started"]:
            if math.isnan(x):
                st["value"] = None
                return None
            st["started"] = True
        if not st["seeded"]:
            if not math.isnan(x):
                st["seed_buf"].append(x)
            if len(st["seed_buf"]) < period:
                st["value"] = None
                return None
            seed = sum(st["seed_buf"][:period]) / period
            st["rma"] = seed
            st["seeded"] = True
            st["value"] = seed
            st["seed_buf"] = []
            return seed
        if math.isnan(x):
            st["value"] = st["rma"]
            return st.get("value")
        st["rma"] = alpha * x + (1.0 - alpha) * float(st["rma"])
        st["value"] = st["rma"]
        return st.get("value")

    def _rsi_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental RSI using RMA of gains/losses (matches ``_rsi`` structure)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("rsi", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev": None,
                "gain_seed": [],
                "loss_seed": [],
                "avg_gain": None,
                "avg_loss": None,
                "seeded": False,
                "value": None,
            }
            bucket[key] = st
        raw = self._series_last(series)
        try:
            x = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            x = None
        prev = st["prev"]
        st["prev"] = x
        if prev is None:
            st["value"] = None
            return None
        if x is None:
            gain, loss = 0.0, 0.0
        else:
            change = x - prev
            gain = change if change > 0 else 0.0
            loss = -change if change < 0 else 0.0
        alpha = 1.0 / period
        if not st["seeded"]:
            st["gain_seed"].append(gain)
            st["loss_seed"].append(loss)
            if len(st["gain_seed"]) < period:
                st["value"] = None
                return None
            st["avg_gain"] = sum(st["gain_seed"][:period]) / period
            st["avg_loss"] = sum(st["loss_seed"][:period]) / period
            st["seeded"] = True
            st["gain_seed"] = []
            st["loss_seed"] = []
        else:
            st["avg_gain"] = alpha * gain + (1.0 - alpha) * float(st["avg_gain"])
            st["avg_loss"] = alpha * loss + (1.0 - alpha) * float(st["avg_loss"])
        avg_gain = float(st["avg_gain"])
        avg_loss = float(st["avg_loss"])
        if avg_loss == 0.0:
            st["value"] = 100.0
        else:
            rs = avg_gain / avg_loss
            st["value"] = 100.0 - (100.0 / (1.0 + rs))
        return st.get("value")

    @staticmethod
    def _ema_state_new() -> dict[str, Any]:
        return {"ema": None, "seeded": False}

    @staticmethod
    def _ema_state_step(st: dict[str, Any], x: Any, period: int) -> float | None:
        """One EMA sample step matching full ``_ema`` (no call-site slot)."""
        if period <= 0:
            return None
        alpha = 2.0 / (period + 1)
        if not st["seeded"]:
            if x is None:
                return None
            st["ema"] = float(x)
            st["seeded"] = True
            return st["ema"]
        if x is None:
            return st.get("ema")
        prev = st["ema"]
        if prev is None:
            st["ema"] = float(x)
        else:
            st["ema"] = alpha * float(x) + (1.0 - alpha) * float(prev)
        return st.get("ema")

    def _macd_inc_update(
        self,
        series: list[Any],
        fast: int,
        slow: int,
        signal: int,
    ) -> tuple[float, float, float]:
        """Incremental MACD matching full ``_macd`` (last macd/signal/hist).

        Uses one call-site slot with three internal EMA states (fast/slow/signal).
        """
        if fast <= 0 or slow <= 0 or signal <= 0:
            return 0.0, 0.0, 0.0
        slot = self._ta_next_slot()
        key = ("macd", slot, fast, slow, signal)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "fast": self._ema_state_new(),
                "slow": self._ema_state_new(),
                "sig": self._ema_state_new(),
            }
            bucket[key] = st
        x = self._series_last(series)
        ef = self._ema_state_step(st["fast"], x, fast)
        es = self._ema_state_step(st["slow"], x, slow)
        if ef is None or es is None:
            macd_val: float | None = None
        else:
            macd_val = float(ef) - float(es)
        sig_val = self._ema_state_step(st["sig"], macd_val, signal)
        if macd_val is None:
            last_macd = 0.0
        else:
            last_macd = float(macd_val)
        last_signal = float(sig_val) if sig_val is not None else 0.0
        if macd_val is not None and sig_val is not None:
            last_hist = float(macd_val) - float(sig_val)
        else:
            last_hist = 0.0
        return last_macd, last_signal, last_hist

    def _atr_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
    ) -> float | None:
        """Incremental ATR matching full ``_atr`` (EMA of TR after warm-up).

        Full path: while ``len(tr) < period`` return mean(tr); once
        ``len(tr) >= period`` return ``_ema(tr, period)[-1]``.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("atr", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_close": None,
                "trs": [],
                "ema": self._ema_state_new(),
                "ema_mode": False,
                "value": None,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        prev_c = st["prev_close"]
        st["prev_close"] = c
        if prev_c is None:
            st["value"] = None
            return None
        if h is None or l is None or c is None:
            st["value"] = None
            return st.get("value")
        try:
            tr = max(
                float(h) - float(l),
                abs(float(h) - float(prev_c)),
                abs(float(l) - float(prev_c)),
            )
        except (TypeError, ValueError):
            st["value"] = None
            return None
        if not st["ema_mode"]:
            st["trs"].append(tr)
            if len(st["trs"]) < period:
                st["value"] = statistics.mean(st["trs"])
                return st["value"]
            # Bootstrap EMA over all TR samples so far (matches full _ema(tr, period))
            for t in st["trs"]:
                self._ema_state_step(st["ema"], t, period)
            st["ema_mode"] = True
            st["trs"] = []
            st["value"] = st["ema"].get("ema")
            return st.get("value")
        st["value"] = self._ema_state_step(st["ema"], tr, period)
        return st.get("value")

    def _stdev_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental sample stdev matching full ``_stdev`` (last value).

        Uses running sum / sum-of-squares over the non-None samples in the
        period window (``statistics.stdev`` sample variance, ddof=1).
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("stdev", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "sumsq": 0.0, "count": 0, "value": None}
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None
        if raw is None:
            x = None
        else:
            try:
                x = float(raw)
            except (TypeError, ValueError):
                x = None
        window: deque[float | None] = st["window"]
        if len(window) == period:
            old = window.popleft()
            if old is not None:
                st["sum"] -= old
                st["sumsq"] -= old * old
                st["count"] -= 1
        window.append(x)
        if x is not None:
            st["sum"] += x
            st["sumsq"] += x * x
            st["count"] += 1
        n = int(st["count"])
        if len(window) < period or n < 2:
            st["value"] = None
            return None
        # sample variance: (sumsq - sum^2/n) / (n-1)
        s = float(st["sum"])
        ss = float(st["sumsq"])
        var = (ss - (s * s) / n) / (n - 1)
        if var < 0.0:
            # floating-point cancellation guard
            var = 0.0
        st["value"] = math.sqrt(var)
        return st.get("value")

    def _highest_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental highest matching full ``_highest`` (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("highest", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        if len(window) == period:
            window.popleft()
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        best: float | None = None
        for v in window:
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best is None or fv > best:
                best = fv
        st["value"] = best
        return best

    def _lowest_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental lowest matching full ``_lowest`` (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("lowest", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        if len(window) == period:
            window.popleft()
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        best: float | None = None
        for v in window:
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best is None or fv < best:
                best = fv
        st["value"] = best
        return best

    def _wma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental WMA matching full ``_wma`` (last value).

        Weights positions 1..period within the window (oldest weight 1).
        None samples are dropped from the weighted sum (same as full path).
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("wma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        if len(window) == period:
            window.popleft()
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        # Match full path: if any None, weight by (i+1) among full period positions
        # for non-None only; else classic 1..period weights.
        has_none = any(v is None for v in window)
        if has_none:
            valid = [(i + 1, v) for i, v in enumerate(window) if v is not None]
            if not valid:
                st["value"] = None
                return None
            total_w = sum(w for w, _ in valid)
            st["value"] = sum(w * float(v) for w, v in valid) / total_w
            return st.get("value")
        # series[-1]*period + series[-2]*(period-1) + ... + series[-period]*1
        total_w = period * (period + 1) / 2.0
        acc = 0.0
        for i, v in enumerate(window):
            acc += float(v) * (i + 1)
        st["value"] = acc / total_w
        return st.get("value")

    def _tr_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
    ) -> float | None:
        """Incremental True Range last value (matches ``_tr`` bar-mode finalize).

        First bar is always ``None`` (full path seeds ``[None, ...]``).
        """
        slot = self._ta_next_slot()
        key = ("tr", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"prev_close": None, "started": False, "value": None}
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        prev_c = st["prev_close"]
        st["prev_close"] = c
        if not st["started"]:
            # First sample: no TR (matches full ``_tr`` result[0] = None)
            st["started"] = True
            st["value"] = None
            return None
        if h is None or l is None or prev_c is None:
            st["value"] = None
            return None
        try:
            tr = max(
                float(h) - float(l),
                abs(float(h) - float(prev_c)),
                abs(float(l) - float(prev_c)),
            )
        except (TypeError, ValueError):
            st["value"] = None
            return None
        st["value"] = tr
        return tr

    def _change_inc_update(self, source: list[Any], length: int = 1) -> float | None:
        """Incremental ``ta.change`` matching full ``_change`` (last value)."""
        if length < 0:
            return None
        if length == 0:
            # change over 0 bars is always 0 when source defined
            x = self._series_last(source)
            if x is None:
                return None
            try:
                float(x)
            except (TypeError, ValueError):
                return None
            return 0.0
        slot = self._ta_next_slot()
        key = ("change", slot, length)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=length + 1), "value": None}
            bucket[key] = st
        x = self._series_last(source)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) <= length:
            st["value"] = None
            return None
        a, b = window[-1], window[0]
        if a is None or b is None:
            st["value"] = None
            return None
        try:
            st["value"] = float(a) - float(b)
        except (TypeError, ValueError):
            st["value"] = None
        return st.get("value")

    def _finalize_series(self, values: list[Any]) -> Any:
        """Return full series list, or current scalar in bar mode."""
        if not self._bar_mode():
            return values
        if not values:
            return None
        return values[-1]

    def _cap_series_list(self, series: list[Any]) -> list[Any]:
        """Return chronological series capped to ``_SERIES_MAX`` (no copy if short)."""
        n = len(series)
        if n > self._SERIES_MAX:
            return series[-self._SERIES_MAX :]
        return series

    def _as_series(self, value: Any) -> list[Any]:
        """Convert a Pine-series-like object to a list.

        Accepts:
        - ``list`` — returned as-is (capped to ``_SERIES_MAX``).
        - Any object with a ``history`` attribute (e.g. ``PineSeries``) —
          its history is converted to a reversed list (chronological order),
          truncated to the most recent ``_SERIES_MAX`` elements to avoid
          O(n²) recomputation of full history at every bar.
        - Falls back to ``self.current_series`` lookup by name when the
          value is a string matching a known key.
        - Otherwise wraps the value in a single-element list.
        """
        if isinstance(value, list):
            return self._cap_series_list(value)
        # Duck-type PineSeries: has a deque/iterable history
        if hasattr(value, "history"):
            raw = list(reversed(value.history))
            if len(raw) > self._SERIES_MAX:
                raw = raw[-self._SERIES_MAX :]
            return raw
        # Named series reference — look up from the pre-loaded dict
        series_map = getattr(self, "current_series", None) or {}
        if isinstance(value, str) and value in series_map:
            src = series_map[value]
            # Prefer view/cap without full copy when already a list
            if isinstance(src, list):
                return self._cap_series_list(src)
            return list(src)
        # Unknown — wrap as single-element
        return [value]

    def _context_series(self, name: str) -> list[Any]:
        """Return a named OHLCV series from the bar runtime context.

        Used when Pine calls omit the source series, e.g. ``ta.highest(20)``
        (defaults to high) or ``ta.atr(14)`` (uses high/low/close).
        """
        series_map = getattr(self, "current_series", None) or {}
        if name in series_map and series_map[name]:
            src = series_map[name]
            if isinstance(src, list):
                return self._cap_series_list(src)
            return list(src)
        # Fall back to empty — callers treat short series as na
        return []

    def _is_period_like(self, value: Any) -> bool:
        """True if *value* looks like a length/period (int or whole float)."""
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float) and value == int(value):
            return True
        return False

    def _expect_series(
        self,
        args: list[Any],
        length: int,
        *,
        default_source: str | None = "close",
        allow_period_only: bool = False,
    ) -> tuple[list[Any], int]:
        """Validate and extract series and period arguments.

        TradingView allows ``ta.sma(close, 14)`` and, for some functions,
        ``ta.highest(14)`` (period-only, source defaults to high/low/close).

        When ``allow_period_only`` is True and a single period-like arg is
        passed, the series is taken from ``current_series[default_source]``.
        """
        if allow_period_only and len(args) == 1 and self._is_period_like(args[0]):
            if not default_source:
                self._error(f"ta.* function requires {length} argument(s), got 1. Expected: (series, period)")
            series = self._context_series(default_source)
            period = self._expect_int(args[0], "Period must be an integer")
            return series, period
        if len(args) != length:
            self._error(f"ta.* function requires {length} argument(s), got {len(args)}. Expected: (series, period)")
        series = self._as_series(args[0])
        # If caller passed a scalar as "series" (e.g. intermediate expression),
        # wrap and continue — period must still resolve.
        period = self._expect_int(
            args[1],
            "Second argument must be an integer (period)",
        )
        return series, period

    def _expect_two_series(
        self,
        args: list[Any],
    ) -> tuple[list[Any], list[Any]]:
        """Validate and extract two series arguments."""
        if len(args) != BINARY:
            self._error("Function takes two series arguments")
        return (
            self._as_series(args[0]),
            self._as_series(args[1]),
        )

    def _expect_int(self, value: Any, message: str) -> int:
        """Validate that value is an integer (accepts floats via floor for periods)."""
        # Unwrap series wrappers / input dict defaults / single-element lists / na
        if isinstance(value, dict) and "default" in value:
            value = value["default"]
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
            # PineSeries / _SeriesResult / _NaValue-like
            cur = value.current
            # _NaValue is callable and has no numeric current
            if type(value).__name__ == "_NaValue":
                self._error(f"{message}. Got: na")
            value = cur
        if isinstance(value, list):
            if not value:
                self._error(f"{message}. Got: empty series")
            # series length expressions → use current (last) bar
            value = value[-1]
        if value is None:
            self._error(f"{message}. Got: na")
        if isinstance(value, float):
            # TV floors fractional periods (e.g. length/2 → 4 for length=9)
            value = int(math.floor(value))
        if isinstance(value, bool):
            value = int(value)
        # String digits (rare, from input/str.tonumber paths)
        if isinstance(value, str):
            try:
                value = int(float(value))
            except ValueError:
                self._error(f"{message}. Got: str")
        if not isinstance(value, int):
            self._error(f"{message}. Got: {type(value).__name__}")
        return value

    def _expect_number(self, value: Any, message: str) -> float:
        """Validate that value is numeric and return as float."""
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes, int, float)):
            value = value.current
        if isinstance(value, list) and value:
            value = value[-1]
        if not isinstance(value, int | float):
            self._error(f"{message}. Got: {type(value).__name__}")
        return float(value)

    # Helper methods used across multiple indicators

    def _min_series(
        self,
        series: list[Any],
        period: int,
    ) -> list[float | None]:
        """Calculate minimum value over rolling period."""
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
        """Calculate maximum value over rolling period."""
        result: list[float | None] = []
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            valid = [value for value in window if value is not None]
            result.append(max(valid) if valid else None)
        return result

    def _format_series(self, series: list[Any]) -> list[float]:
        """Convert series to float list, replacing None with NaN."""
        return [float(value) if value is not None else math.nan for value in series]

    def _sma(self, series: list[Any], period: int) -> list[float | None]:
        """Simple Moving Average."""
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
        """Exponential Moving Average."""
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

    def _rma(self, series: list[Any], period: int) -> list[float]:
        """Recursive Moving Average (Wilder's Smoothing)."""
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

    def _wma(self, series: list[float], period: int) -> float | None:
        """Weighted Moving Average (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = series[-period:]
        if any(v is None for v in window):
            valid = [(i + 1, v) for i, v in enumerate(window) if v is not None]
            if not valid:
                return None
            # weight by position among full period (TV drops na bars from sum only)
            total_w = sum(w for w, _ in valid)
            return sum(w * float(v) for w, v in valid) / total_w
        weights = list(range(1, period + 1))
        total = sum(weights)
        return sum(float(series[-idx]) * (period - idx + 1) for idx in range(1, period + 1)) / total

    def _highest(self, series: list[float], period: int) -> float | None:
        """Get highest value in period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [v for v in series[-period:] if v is not None]
        return max(window) if window else None

    def _lowest(self, series: list[float], period: int) -> float | None:
        """Get lowest value in period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [v for v in series[-period:] if v is not None]
        return min(window) if window else None

    def _stdev(self, series: list[float], period: int) -> float | None:
        """Standard deviation over period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [float(v) for v in series[-period:] if v is not None]
        if len(window) < 2:
            return None
        return statistics.stdev(window)

    def _tr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> list[float | None]:
        """True Range calculation (na-safe)."""
        if not closes:
            return []
        result: list[float | None] = [None]
        for idx in range(1, len(closes)):
            h, l, c_prev = highs[idx] if idx < len(highs) else None, lows[idx] if idx < len(lows) else None, closes[idx - 1]
            if h is None or l is None or c_prev is None:
                result.append(None)
                continue
            try:
                result.append(
                    max(
                        float(h) - float(l),
                        abs(float(h) - float(c_prev)),
                        abs(float(l) - float(c_prev)),
                    )
                )
            except (TypeError, ValueError):
                result.append(None)
        return result

    @staticmethod
    def _cmp_lt(a: Any, b: Any) -> bool | None:
        if a is None or b is None:
            return None
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cmp_gt(a: Any, b: Any) -> bool | None:
        if a is None or b is None:
            return None
        try:
            return float(a) > float(b)
        except (TypeError, ValueError):
            return None

    def _crossover(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses above series2 (na-safe)."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_lt(series1[-2], series2[-2])
        curr = self._cmp_gt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _crossunder(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses below series2 (na-safe)."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_gt(series1[-2], series2[-2])
        curr = self._cmp_lt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _cross_stateful(
        self,
        series1: list[Any],
        series2: list[Any],
        *,
        under: bool,
    ) -> bool:
        """Bar-mode crossover when args are scalars (history length 1).

        Runtime sets ``_cross_call_i = 0`` each bar and keeps ``_cross_state``
        across bars: map call-index → previous (s1, s2) pair.
        """
        a = series1[-1] if series1 else None
        b = series2[-1] if series2 else None
        try:
            a_f = float(a) if a is not None else None
            b_f = float(b) if b is not None else None
        except (TypeError, ValueError):
            a_f, b_f = None, None

        i = int(getattr(self, "_cross_call_i", 0) or 0)
        state: dict[int, tuple[Any, Any]] = getattr(self, "_cross_state", None) or {}
        prev = state.get(i)
        result = False
        if (
            prev is not None
            and prev[0] is not None
            and prev[1] is not None
            and a_f is not None
            and b_f is not None
        ):
            try:
                pa, pb = float(prev[0]), float(prev[1])
                if under:
                    # was above or equal, now strictly below
                    result = pa >= pb and a_f < b_f
                else:
                    # was below or equal, now strictly above
                    result = pa <= pb and a_f > b_f
            except (TypeError, ValueError):
                result = False

        state[i] = (a_f, b_f)
        self._cross_state = state  # type: ignore[attr-defined]
        self._cross_call_i = i + 1  # type: ignore[attr-defined]
        return result

    def _cross(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses series2 (either direction)."""
        return bool(self._crossover(series1, series2) or self._crossunder(series1, series2))

    def _falling(self, series: list[float], period: int) -> bool:
        """Check if series is falling for period (na-safe)."""
        if len(series) < period or period < 1:
            return False
        for idx in range(1, period):
            cmp = self._cmp_lt(series[-idx], series[-idx - 1])  # current < previous? falling means lower
            # falling: series[-idx] < series[-idx-1] is wrong; falling means each is lower than previous
            # i.e. series[-1] < series[-2] < ... 
            a, b = series[-idx], series[-idx - 1]
            if a is None or b is None:
                return False
            try:
                if float(a) >= float(b):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _rising(self, series: list[float], period: int) -> bool:
        """Check if series is rising for period (na-safe)."""
        if len(series) < period or period < 1:
            return False
        for idx in range(1, period):
            a, b = series[-idx], series[-idx - 1]
            if a is None or b is None:
                return False
            try:
                if float(a) <= float(b):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _highestbars(self, series: list[float], period: int) -> int:
        """Get offset to highest value in period."""
        if len(series) < period:
            return -1
        window = series[-period:]
        valid = [(i, v) for i, v in enumerate(window) if v is not None]
        if not valid:
            return -1
        max_i, _ = max(valid, key=lambda iv: iv[1])
        return -(period - 1 - max_i)

    def _lowestbars(self, series: list[float], period: int) -> int:
        """Get offset to lowest value in period."""
        if len(series) < period:
            return -1
        window = series[-period:]
        valid = [(i, v) for i, v in enumerate(window) if v is not None]
        if not valid:
            return -1
        min_i, _ = min(valid, key=lambda iv: iv[1])
        return -(period - 1 - min_i)

    def _swma(self, series: list[Any]) -> float | None:
        """Symmetrically Weighted Moving Average (4-period: 1/6, 2/6, 2/6, 1/6)."""
        if len(series) < 4:
            return None
        w = series[-4:]
        if any(v is None for v in w):
            return None
        try:
            return (float(w[0]) + 2 * float(w[1]) + 2 * float(w[2]) + float(w[3])) / 6.0
        except (TypeError, ValueError):
            return None

    def _change(self, source: list[float], length: int = 1) -> float | None:
        """Calculate change over length (na-safe)."""
        if len(source) <= length:
            return None
        a, b = source[-1], source[-1 - length]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None

    def _mom(self, series: list[float], period: int) -> float | None:
        """Calculate momentum (na-safe)."""
        if len(series) <= period:
            return None
        a, b = series[-1], series[-period - 1]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None
