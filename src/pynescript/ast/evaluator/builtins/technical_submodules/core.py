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

"""Shared helpers for all ``ta.*`` indicator submodules.

Provides arity constants, series/period coercion (via
:func:`~pynescript.ast.evaluator.builtins.base.pine_expect_int` /
:func:`~pynescript.ast.evaluator.builtins.base.pine_period_or_none`),
incremental-TA toggles, and :class:`TechnicalHelpers` — the base class for
every indicator mixin under this package.

Composition
-----------
Indicator modules inherit :class:`TechnicalHelpers` and are aggregated by
:class:`~pynescript.ast.evaluator.builtins.technical.TechnicalAnalysisMixin`.
"""

from __future__ import annotations

import math
import os
import statistics

from collections import deque
from typing import Any

from pynescript.ast.evaluator.builtins.base import pine_expect_int
from pynescript.ast.evaluator.builtins.base import pine_period_or_none


# Constants
UNARY = 1
BINARY = 2
TERNARY = 3
QUATERNARY = 4
QUINARY = 5

MIN_SERIES_LENGTH = 2

# Sentinel for ``_series_last`` getattr default (distinct from None / na).
_MISSING: Any = object()


class TechnicalHelpers:
    """Base utilities for ``ta.*`` handlers (series expect, SMA helpers, state).

    Subclasses implement ``_builtin_ta_*`` methods. Expects evaluator attributes
    such as ``current_series``, ``context``, and ``_error`` when composed into
    the full evaluator via :class:`TechnicalAnalysisMixin`.
    """

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
    def _series_last(series: Any) -> Any:
        """Current-bar source sample (bar mode feeds one update per call).

        Accepts:
        - ``list`` / sequence — last element
        - objects with ``.current`` (e.g. ``PineSeries``)
        - objects with newest-first ``.history`` (deque) — ``history[0]``
        - bare scalars — returned as-is

        Fast paths for ``list`` / ``float`` / ``int`` / ``None`` avoid
        ``getattr`` on the pure-incremental TA hot path.
        """
        t = type(series)
        if t is list:
            return series[-1] if series else None
        if series is None or t is float or t is int or t is bool:
            return series
        # PineSeries / series wrapper: prefer .current (avoids history access)
        current = getattr(series, "current", _MISSING)
        if current is not _MISSING:
            return current
        hist = getattr(series, "history", None)
        if hist is not None:
            try:
                if len(hist) == 0:
                    return None
                # Newest-first (PineSeries deque) → index 0 is current bar
                return hist[0]
            except TypeError:
                pass
        return series

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
        # Strict window (match compile numba_sma / reference Pine): any na in the length
        # window → na. Require count == period (every slot finite).
        if len(window) < period or st["count"] != period:
            st["value"] = None
        else:
            st["value"] = st["sum"] / period
        return st.get("value")

    def _sum_inc_update(self, series: Any, period: int) -> float | None:
        """Incremental rolling sum matching ``numba_sum_inc`` / reference Pine ``math.sum``.

        Full window required; any na/NaN in the window → na (poison). Works from
        scalar samples via call-site state (same pattern as ``_sma_inc_update``),
        so user series that are bare floats still accumulate correctly.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("sum", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "na_count": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        is_na = x is None
        xf = 0.0
        if not is_na:
            try:
                xf = float(x)
                if xf != xf:  # NaN
                    is_na = True
                    xf = 0.0
            except (TypeError, ValueError):
                is_na = True
                xf = 0.0
        window: deque[tuple[bool, float]] = st["window"]
        if len(window) == period:
            old_na, old_v = window.popleft()
            if old_na:
                st["na_count"] -= 1
            else:
                st["sum"] -= old_v
        window.append((is_na, xf))
        if is_na:
            st["na_count"] += 1
        else:
            st["sum"] += xf
        if len(window) < period or st["na_count"] > 0:
            st["value"] = None
        else:
            st["value"] = st["sum"]
        return st.get("value")

    def _ema_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental EMA with SMA seed (matches ``numba_ema_inc`` / reference Pine).

        Seed = mean of first ``period`` finite samples; na until the window is
        full. Prior first-value seed diverged from compile on Chaikin Osc etc.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("ema", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "ema": None,
                "seeded": False,
                "seed_buf": [],
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        # Soft-fail non-numeric samples (unresolved source-name strings, colors)
        # to na rather than ``float('obv')`` Runtime Error.
        if x is not None and type(x) is not float and type(x) is not int:
            try:
                x = float(x)
            except (TypeError, ValueError):
                x = None
        alpha = 2.0 / (period + 1)
        if not st["seeded"]:
            if x is None:
                st["value"] = None
                return None
            st["seed_buf"].append(float(x))
            if len(st["seed_buf"]) < period:
                st["value"] = None
                return None
            seed = sum(st["seed_buf"][:period]) / period
            st["ema"] = seed
            st["seeded"] = True
            st["value"] = seed
            # free seed buffer
            st["seed_buf"] = []
            return seed
        if x is None:
            return st.get("ema")
        prev = st["ema"]
        if prev is None:
            st["ema"] = float(x)
        else:
            st["ema"] = alpha * float(x) + (1.0 - alpha) * float(prev)
        st["value"] = st["ema"]
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
        return {"ema": None, "seeded": False, "seed_buf": []}

    @staticmethod
    def _ema_state_step(st: dict[str, Any], x: Any, period: int) -> float | None:
        """One EMA sample step matching full ``_ema`` / ``_ema_inc_update`` (SMA seed)."""
        if period <= 0:
            return None
        alpha = 2.0 / (period + 1)
        if not st["seeded"]:
            if x is None:
                return None
            buf = st.setdefault("seed_buf", [])
            buf.append(float(x))
            if len(buf) < period:
                return None
            seed = sum(buf[:period]) / period
            st["ema"] = seed
            st["seeded"] = True
            st["seed_buf"] = []
            return seed
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
        """Incremental ATR matching full ``_atr`` (Wilder RMA of TR).

        Reference Pine: ``ta.atr(length)`` ≡ ``ta.rma(ta.tr, length)``. Dual-host aligned
        with ``numba_atr`` / ``numba_atr_inc`` (audit Wave B).
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
                "rma": self._rma_state_new(),
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
        st["value"] = self._rma_state_step(st["rma"], tr, period)
        return st.get("value")

    def _stdev_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental sample stdev matching full ``_stdev`` (last value).

        Strict window (match compile ``numba_stdev`` / reference / ``_sma``): any ``na``
        in the length window yields ``na``. Sample variance uses ddof=1 over the
        full ``period`` finite samples (requires ``period >= 2``).
        """
        if period <= 1:
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
                if x != x:  # NaN
                    x = None
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
        # Require every slot finite (count == period), same as SMA strict window.
        if len(window) < period or n != period:
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
        """Incremental WMA matching full ``_wma`` / compile ``numba_wma``.

        Weights positions 1..period within the window (oldest weight 1).
        Requires a full window of non-``na`` samples (reference / compile parity);
        any ``None`` in the window → ``na``.
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
        # Full window required — do not drop na and reweight (that drifted
        # Coppock / nested WMA vs compile).
        if any(v is None for v in window):
            st["value"] = None
            return None
        # series[-1]*period + series[-2]*(period-1) + ... + series[-period]*1
        total_w = period * (period + 1) / 2.0
        acc = 0.0
        for i, v in enumerate(window):
            try:
                acc += float(v) * (i + 1)
            except (TypeError, ValueError):
                st["value"] = None
                return None
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

    def _stoch_k_inc_update(
        self,
        source: list[Any],
        highs: list[Any],
        lows: list[Any],
        length: int,
    ) -> float | None:
        """Incremental Stochastic %K matching ``_stoch_k`` (last bar)."""
        if length <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("stoch_k", slot, length)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h_win": deque(maxlen=length),
                "l_win": deque(maxlen=length),
                "value": None,
            }
            bucket[key] = st
        c = self._series_last(source)
        h = self._series_last(highs)
        l = self._series_last(lows)
        h_win: deque[Any] = st["h_win"]
        l_win: deque[Any] = st["l_win"]
        h_win.append(h)
        l_win.append(l)
        # Match full ``_stoch_k``: use available history (partial window OK).
        window_h = [v for v in h_win if v is not None]
        window_l = [v for v in l_win if v is not None]
        if c is None or not window_h or not window_l:
            st["value"] = None
            return None
        try:
            hh = max(float(v) for v in window_h)
            ll = min(float(v) for v in window_l)
            if hh == ll:
                st["value"] = 50.0
                return 50.0
            st["value"] = 100.0 * (float(c) - ll) / (hh - ll)
        except (TypeError, ValueError):
            st["value"] = None
        return st.get("value")

    def _cum_inc_update(self, series: list[Any]) -> float | None:
        """Incremental cumulative sum matching bar-mode ``ta.cum`` (last value).

        reference Pine treats ``na`` as 0 (same as compile ``numba_cum_expr``), so a
        pure-na source (e.g. foreign ``request.security`` without data) yields
        0 rather than lingering ``na``.
        """
        slot = self._ta_next_slot()
        key = ("cum", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"total": 0.0, "value": 0.0}
            bucket[key] = st
        x = self._series_last(series)
        # reference Pine: na / IEEE NaN → 0 contribution (compile ``numba_cum_expr`` same).
        add = 0.0
        if x is not None:
            try:
                fx = float(x)
                if fx == fx:  # not NaN
                    add = fx
            except (TypeError, ValueError):
                add = 0.0
        st["total"] = float(st["total"]) + add
        st["value"] = st["total"]
        return st.get("value")

    def _vwma_inc_update(
        self,
        series: list[Any],
        volume: list[Any],
        period: int,
    ) -> float | None:
        """Incremental volume-weighted MA: sum(src*vol)/sum(vol) over period."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("vwma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "s_win": deque(maxlen=period),
                "v_win": deque(maxlen=period),
                "sum_pv": 0.0,
                "sum_v": 0.0,
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        v = self._series_last(volume) if volume else None
        s_win: deque[Any] = st["s_win"]
        v_win: deque[Any] = st["v_win"]
        # Dropping old sample from running sums when window full
        if len(s_win) == period:
            old_s = s_win[0]
            old_v = v_win[0]
            if old_s is not None and old_v is not None:
                try:
                    st["sum_pv"] -= float(old_s) * float(old_v)
                    st["sum_v"] -= float(old_v)
                except (TypeError, ValueError):
                    pass
        s_win.append(x)
        v_win.append(v)
        if x is not None and v is not None:
            try:
                st["sum_pv"] += float(x) * float(v)
                st["sum_v"] += float(v)
            except (TypeError, ValueError):
                st["value"] = None
                return None
        if len(s_win) < period:
            st["value"] = None
            return None
        # Any None in window → recompute carefully (match NaN windows)
        if any(a is None or b is None for a, b in zip(s_win, v_win, strict=True)):
            sp = 0.0
            sv = 0.0
            for a, b in zip(s_win, v_win, strict=True):
                if a is None or b is None:
                    st["value"] = None
                    return None
                try:
                    sp += float(a) * float(b)
                    sv += float(b)
                except (TypeError, ValueError):
                    st["value"] = None
                    return None
            st["sum_pv"] = sp
            st["sum_v"] = sv
        if st["sum_v"] == 0.0:
            st["value"] = None
            return None
        st["value"] = st["sum_pv"] / st["sum_v"]
        return st.get("value")

    def _cci_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
    ) -> float:
        """Incremental CCI matching full ``_cci`` (last value).

        Window of typical price; SMA via running sum; mean absolute deviation
        recomputed over the window each bar (O(period)). Full path returns
        ``0.0`` when under-warmed or mean deviation is zero/undefined.
        """
        if period <= 0:
            return 0.0
        slot = self._ta_next_slot()
        key = ("cci", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "window": deque(),
                "sum": 0.0,
                "count": 0,
                "last_mean_dev": None,  # last non-zero mean abs dev
                "value": 0.0,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        tp: float | None
        if h is None or l is None or c is None:
            tp = None
        else:
            try:
                tp = (float(h) + float(l) + float(c)) / 3.0
            except (TypeError, ValueError):
                tp = None
        window: deque[float | None] = st["window"]
        if len(window) == period:
            old = window.popleft()
            if old is not None:
                st["sum"] -= old
                st["count"] -= 1
        window.append(tp)
        if tp is not None:
            st["sum"] += tp
            st["count"] += 1
        if len(window) < period or st["count"] <= 0:
            st["value"] = 0.0
            return 0.0
        sma = float(st["sum"]) / int(st["count"])
        # Mean abs dev over non-None samples vs current SMA (matches full path)
        acc = 0.0
        n_valid = 0
        for v in window:
            if v is None:
                continue
            acc += abs(float(v) - sma)
            n_valid += 1
        if n_valid <= 0:
            st["value"] = 0.0
            return 0.0
        mean_dev = acc / n_valid
        if mean_dev not in {None, 0, 0.0}:
            st["last_mean_dev"] = mean_dev
        last_mean_dev = st["last_mean_dev"]
        if last_mean_dev is None or last_mean_dev == 0:
            st["value"] = 0.0
            return 0.0
        last_tp = next((v for v in reversed(window) if v is not None), 0.0)
        st["value"] = (float(last_tp) - sma) / (0.015 * float(last_mean_dev))
        return st["value"]

    def _tsi_inc_update(
        self,
        series: list[Any],
        long_period: int,
        short_period: int,
    ) -> float | None:
        """Incremental TSI matching full ``_tsi`` (double EMA of mom / |mom|).

        Full path returns ``None`` while ``len(series) < long + short``.
        """
        if long_period <= 0 or short_period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("tsi", slot, long_period, short_period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev": None,
                "n_bars": 0,
                "ema_mom": self._ema_state_new(),
                "ema_ema_mom": self._ema_state_new(),
                "ema_abs": self._ema_state_new(),
                "ema_ema_abs": self._ema_state_new(),
                "value": None,
            }
            bucket[key] = st
        raw = self._series_last(series)
        try:
            x = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            x = None
        st["n_bars"] = int(st["n_bars"]) + 1
        prev = st["prev"]
        st["prev"] = x
        if prev is None or x is None:
            # No momentum yet (or na source); still count bars for warm-up gate
            if int(st["n_bars"]) < long_period + short_period:
                st["value"] = None
                return None
            # After warm-up with missing sample: carry last value
            return st.get("value")
        mom = float(x) - float(prev)
        abs_mom = abs(mom)
        e1 = self._ema_state_step(st["ema_mom"], mom, long_period)
        e2 = self._ema_state_step(st["ema_ema_mom"], e1, short_period)
        a1 = self._ema_state_step(st["ema_abs"], abs_mom, long_period)
        a2 = self._ema_state_step(st["ema_ema_abs"], a1, short_period)
        if int(st["n_bars"]) < long_period + short_period:
            st["value"] = None
            return None
        if a2 is None or a2 == 0:
            st["value"] = 0.0 if a2 == 0 else None
            return st.get("value")
        if e2 is None:
            st["value"] = None
            return None
        st["value"] = 100.0 * (float(e2) / float(a2))
        return st.get("value")

    def _roc_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental Rate of Change matching full ``_roc`` / reference Pine ``ta.roc``.

        ``100 * (src - src[period]) / src[period]``. Returns ``None`` when
        lookback is insufficient or baseline/current is missing/zero (parity
        with ``numba_roc``).
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("roc", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            # Need baseline at -(period+1)
            st = {"window": deque(maxlen=period + 1), "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) <= period:
            st["value"] = None
            return None
        # baseline = series[len - period - 1] == window[-(period+1)] == window[0]
        baseline = window[0]
        current = window[-1]
        if baseline in {None, 0} or current is None:
            st["value"] = None
            return None
        try:
            b = float(baseline)
            c = float(current)
            if b == 0.0:
                st["value"] = None
                return None
            st["value"] = 100.0 * (c - b) / b
        except (TypeError, ValueError, ZeroDivisionError):
            st["value"] = None
            return None
        return float(st["value"])

    def _wpr_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
    ) -> float:
        """Incremental Williams %R matching full ``_wpr`` (last value).

        Full path returns ``0.0`` when under-warmed or high==low.
        """
        if period <= 0:
            return 0.0
        slot = self._ta_next_slot()
        key = ("wpr", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h_win": deque(maxlen=period),
                "l_win": deque(maxlen=period),
                "value": 0.0,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        h_win: deque[Any] = st["h_win"]
        l_win: deque[Any] = st["l_win"]
        h_win.append(h)
        l_win.append(l)
        if len(h_win) < period:
            st["value"] = 0.0
            return 0.0
        try:
            # Match full path: max/min over raw window (no None filter)
            hh = max(float(v) for v in h_win)
            ll = min(float(v) for v in l_win)
            if hh == ll:
                st["value"] = 0.0
                return 0.0
            if c is None:
                st["value"] = 0.0
                return 0.0
            st["value"] = -100.0 * (hh - float(c)) / (hh - ll)
        except (TypeError, ValueError):
            st["value"] = 0.0
        return float(st["value"])

    def _dev_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental mean absolute deviation matching full ``_dev``.

        Strict window (match compile ``numba_dev`` / reference): any ``na`` → ``na``.
        Running sum for the mean; MAD over the full period window.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("dev", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "count": 0, "value": None}
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None
        if raw is None:
            x = None
        else:
            try:
                x = float(raw)
                if x != x:  # NaN
                    x = None
            except (TypeError, ValueError):
                x = None
        window: deque[float | None] = st["window"]
        if len(window) == period:
            old = window.popleft()
            if old is not None:
                st["sum"] -= old
                st["count"] -= 1
        window.append(x)
        if x is not None:
            st["sum"] += x
            st["count"] += 1
        n = int(st["count"])
        if len(window) < period or n != period:
            st["value"] = None
            return None
        mean = float(st["sum"]) / n
        acc = 0.0
        for v in window:
            if v is None:
                # Defensive: count==period guarantees finite slots
                st["value"] = None
                return None
            acc += abs(float(v) - mean)
        st["value"] = acc / n
        return st.get("value")

    def _variance_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental sample variance matching full ``_variance`` (ddof=1).

        Strict window (match compile ``numba_variance`` / ``_stdev_inc_update``).
        """
        if period <= 1:
            return None
        slot = self._ta_next_slot()
        key = ("variance", slot, period)
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
                if x != x:  # NaN
                    x = None
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
        if len(window) < period or n != period:
            st["value"] = None
            return None
        s = float(st["sum"])
        ss = float(st["sumsq"])
        var = (ss - (s * s) / n) / (n - 1)
        if var < 0.0:
            var = 0.0
        st["value"] = var
        return st.get("value")

    @staticmethod
    def _wma_from_window(window: deque[Any] | list[Any], period: int) -> float | None:
        """WMA over a fixed-length window matching full ``_wma`` last-value rules."""
        if period <= 0 or len(window) < period:
            return None
        has_none = any(v is None for v in window)
        if has_none:
            valid = [(i + 1, v) for i, v in enumerate(window) if v is not None]
            if not valid:
                return None
            total_w = sum(w for w, _ in valid)
            return sum(w * float(v) for w, v in valid) / total_w
        total_w = period * (period + 1) / 2.0
        acc = 0.0
        for i, v in enumerate(window):
            acc += float(v) * (i + 1)
        return acc / total_w

    def _hma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental Hull MA: WMA(2*WMA(n/2)-WMA(n), sqrt(n)) last value.

        One call-site slot owns three windows (half / full / outer). Matches
        full ``_hma`` readiness: first non-None when ``period + sqrt_n - 1``
        samples have been seen.
        """
        if period <= 0:
            return None
        half = max(1, period // 2)
        sqrt_n = max(1, int(math.sqrt(period)))
        slot = self._ta_next_slot()
        key = ("hma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "half_win": deque(maxlen=half),
                "full_win": deque(maxlen=period),
                "diff_win": deque(maxlen=sqrt_n),
                "bars": 0,
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        st["half_win"].append(x)
        st["full_win"].append(x)
        st["bars"] = int(st["bars"]) + 1
        wh = self._wma_from_window(st["half_win"], half)
        wf = self._wma_from_window(st["full_win"], period)
        if wh is None or wf is None:
            st["value"] = None
            return None
        diff = 2.0 * float(wh) - float(wf)
        st["diff_win"].append(diff)
        # Outer WMA needs sqrt_n consecutive valid diffs (full path readiness).
        st["value"] = self._wma_from_window(st["diff_win"], sqrt_n)
        return st.get("value")

    def _rising_inc_update(self, series: list[Any], period: int) -> bool:
        """Incremental ``ta.rising`` matching full ``_rising`` last-value semantics."""
        if period < 1:
            return False
        slot = self._ta_next_slot()
        key = ("rising", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": False}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < period:
            st["value"] = False
            return False
        # Delegate to full helper so MRO / oracle semantics stay identical.
        st["value"] = bool(self._rising(list(window), period))
        return bool(st["value"])

    def _falling_inc_update(self, series: list[Any], period: int) -> bool:
        """Incremental ``ta.falling`` matching full ``_falling`` last-value semantics."""
        if period < 1:
            return False
        slot = self._ta_next_slot()
        key = ("falling", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": False}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < period:
            st["value"] = False
            return False
        st["value"] = bool(self._falling(list(window), period))
        return bool(st["value"])

    def _median_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental rolling median matching full ``_median`` (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("median", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": None}
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
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        valid = sorted(v for v in window if v is not None)
        if not valid:
            st["value"] = None
            return None
        st["value"] = statistics.median(valid)
        return st.get("value")

    def _percentrank_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental percentrank matching full ``_percentrank`` (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("percentrank", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": None}
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
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        valid = sorted(v for v in window if v is not None)
        if not valid or len(valid) < 2:
            st["value"] = 50.0
            return 50.0
        if x is None:
            st["value"] = None
            return None
        count_below = sum(1 for v in valid if v < x)
        st["value"] = (count_below / len(valid)) * 100.0
        return st.get("value")

    def _mom_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental ``ta.mom`` — identical lag math to ``ta.change``."""
        return self._change_inc_update(series, period)

    def _swma_inc_update(self, series: list[Any]) -> float | None:
        """Incremental 4-period SWMA matching full ``_swma`` (last value)."""
        slot = self._ta_next_slot()
        key = ("swma", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=4), "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < 4:
            st["value"] = None
            return None
        w = list(window)
        if any(v is None for v in w):
            st["value"] = None
            return None
        try:
            st["value"] = (float(w[0]) + 2 * float(w[1]) + 2 * float(w[2]) + float(w[3])) / 6.0
        except (TypeError, ValueError):
            st["value"] = None
        return st.get("value")

    def _highestbars_inc_update(self, series: list[Any], period: int) -> int:
        """Incremental highestbars matching full ``_highestbars`` (last offset)."""
        if period <= 0:
            return -1
        slot = self._ta_next_slot()
        key = ("highestbars", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": -1}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < period:
            st["value"] = -1
            return -1
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best_v is None or fv > best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            st["value"] = -1
            return -1
        # Offset from current bar: 0 = current, -1 = previous, ...
        st["value"] = best_i - (period - 1)
        return int(st["value"])

    def _lowestbars_inc_update(self, series: list[Any], period: int) -> int:
        """Incremental lowestbars matching full ``_lowestbars`` (last offset)."""
        if period <= 0:
            return -1
        slot = self._ta_next_slot()
        key = ("lowestbars", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": -1}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < period:
            st["value"] = -1
            return -1
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best_v is None or fv < best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            st["value"] = -1
            return -1
        st["value"] = best_i - (period - 1)
        return int(st["value"])

    def _vwap_inc_update(
        self,
        source: list[Any],
        volume: list[Any] | None = None,
        *,
        anchor: Any = None,
    ) -> float | None:
        """Incremental cumulative VWAP matching bar-mode full recompute last value.

        Sums price*volume / sum(volume) over all bars seen at this call site.
        None prices are skipped (same as full ``_builtin_ta_vwap`` loop).
        When *anchor* is truthy, the cumulative window restarts on this bar.
        """
        slot = self._ta_next_slot()
        key = ("vwap", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"cum_pv": 0.0, "cum_v": 0.0, "value": None, "n": 0}
            bucket[key] = st
        # Anchor reset (ta.vwap(src, anchor)) before adding this bar
        if anchor is not None:
            a = self._series_last(anchor) if not isinstance(anchor, (bool, int, float)) else anchor
            if isinstance(anchor, list):
                a = anchor[-1] if anchor else None
            try:
                if a is not None and bool(a) and not (isinstance(a, float) and a != a):
                    st["cum_pv"] = 0.0
                    st["cum_v"] = 0.0
                    st["n"] = 0
                    st["value"] = None
            except (TypeError, ValueError):
                pass
        price_raw = self._series_last(source)
        if price_raw is None:
            return st.get("value")
        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            return st.get("value")
        v = 0.0
        if volume is not None:
            v_raw = self._series_last(volume)
            if v_raw is not None:
                try:
                    v = float(v_raw)
                except (TypeError, ValueError):
                    v = 0.0
        st["cum_pv"] = float(st["cum_pv"]) + price * v
        st["cum_v"] = float(st["cum_v"]) + v
        st["n"] = int(st["n"]) + 1
        if st["cum_v"]:
            st["value"] = st["cum_pv"] / st["cum_v"]
        else:
            st["value"] = price
        return st.get("value")

    def _barssince_inc_update(self, condition: Any) -> int | None:
        """Incremental ``ta.barssince`` for bar-mode scalar conditions.

        Matches full list-walk semantics when fed one sample per bar:
        - true → 0
        - never true after *k* bars → *k* - 1
        - true then *d* falses → *d*
        """
        slot = self._ta_next_slot()
        key = ("barssince", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"bars_since": 0, "ever_true": False, "bars_seen": 0, "value": None}
            bucket[key] = st

        # Series form: fall back to full scan of provided list (same as non-inc).
        if isinstance(condition, list):
            for i in range(len(condition) - 1, -1, -1):
                c = condition[i]
                is_true = c is True or (c is not None and c is not False)
                if is_true:
                    st["value"] = len(condition) - 1 - i
                    return int(st["value"])
            st["value"] = len(condition) - 1 if condition else None
            return st.get("value")

        is_true = condition is True or (condition is not None and condition is not False)
        st["bars_seen"] = int(st["bars_seen"]) + 1
        if is_true:
            st["ever_true"] = True
            st["bars_since"] = 0
            st["value"] = 0
            return 0
        st["bars_since"] = int(st["bars_since"]) + 1
        if st["ever_true"]:
            st["value"] = int(st["bars_since"])
        else:
            # Never true: list path returns len-1 after k samples → k-1
            st["value"] = int(st["bars_seen"]) - 1
        return int(st["value"])

    def _linreg_inc_update(self, series: list[Any], length: int, offset: int = 0) -> float:
        """Incremental linear-regression endpoint matching full ``ta.linreg``.

        Maintains a rolling window; recomputes slope/intercept on non-None
        samples with x re-indexed 0..m-1 (same as full path / reference / numba).
        Result is the fitted value at ``x = n - 1 - offset``.
        """
        if length < 2:
            return math.nan
        slot = self._ta_next_slot()
        key = ("linreg", slot, length, int(offset))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=length), "value": math.nan}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < length:
            st["value"] = math.nan
            return math.nan
        valid_values: list[float] = []
        for v in window:
            if v is None:
                continue
            try:
                valid_values.append(float(v))
            except (TypeError, ValueError):
                continue
        if len(valid_values) < 2:
            st["value"] = math.nan
            return math.nan
        n = len(valid_values)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(valid_values) / n
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, valid_values, strict=True))
        denominator = sum((xi - mean_x) ** 2 for xi in xs)
        if denominator == 0:
            st["value"] = mean_y
            return mean_y
        slope = numerator / denominator
        # reference Pine: intercept + slope * (n - 1 - offset); intercept = mean_y - slope * mean_x
        st["value"] = mean_y + slope * ((n - 1 - int(offset)) - mean_x)
        return float(st["value"])

    # ------------------------------------------------------------------
    # Round 5 residual incremental kernels (dmi/adx, supertrend, valuewhen,
    # pivots, dema/tema). Nested RMA uses slot-free state helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def _rma_state_new() -> dict[str, Any]:
        return {
            "seed_buf": [],
            "rma": None,
            "seeded": False,
            "started": False,
            "value": None,
        }

    @staticmethod
    def _rma_state_step(st: dict[str, Any], raw: Any, period: int) -> float | None:
        """One RMA sample step matching ``_rma_inc_update`` / full ``_rma``."""
        if period <= 0:
            return None
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

    @staticmethod
    def _is_nan_num(v: Any) -> bool:
        return v is None or (isinstance(v, float) and math.isnan(v))

    def _adx_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
    ) -> float:
        """Incremental ADX matching full ``_adx`` (last non-nan or 0.0).

        Uses nan-first DM (same as ``_adx``), three Wilder RMAs for TR/+DM/-DM
        and a fourth RMA on DX.
        """
        if period <= 0:
            return 0.0
        slot = self._ta_next_slot()
        key = ("adx", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_h": None,
                "prev_l": None,
                "prev_c": None,
                "n": 0,
                "rma_tr": self._rma_state_new(),
                "rma_pdm": self._rma_state_new(),
                "rma_mdm": self._rma_state_new(),
                "rma_dx": self._rma_state_new(),
                "value": 0.0,
            }
            bucket[key] = st

        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        st["n"] = int(st["n"]) + 1
        n = int(st["n"])

        prev_h, prev_l, prev_c = st["prev_h"], st["prev_l"], st["prev_c"]
        st["prev_h"], st["prev_l"], st["prev_c"] = h, l, c

        # True range / DM for this bar (bar 0 of series: TR None, DM nan).
        # Always step RMA state — full path early ``len < period`` only affects
        # the returned value, not the eventual seeded RMA once len grows.
        if prev_c is None or prev_h is None or prev_l is None:
            tr: float | None = None
            plus_dm: float = math.nan
            minus_dm: float = math.nan
        else:
            try:
                hf = float(h) if h is not None else float("nan")
                lf = float(l) if l is not None else float("nan")
                ph = float(prev_h)
                pl = float(prev_l)
                pc = float(prev_c)
                tr = max(hf - lf, abs(hf - pc), abs(lf - pc))
                high_diff = hf - ph
                low_diff = pl - lf
                plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0.0
                minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0.0
            except (TypeError, ValueError):
                tr = None
                plus_dm = math.nan
                minus_dm = math.nan

        atr_v = self._rma_state_step(st["rma_tr"], tr, period)
        pd = self._rma_state_step(st["rma_pdm"], plus_dm, period)
        md = self._rma_state_step(st["rma_mdm"], minus_dm, period)

        # Full ``_adx``: len < period → 0.0 (state still advanced above).
        if n < period:
            st["value"] = 0.0
            return 0.0

        # Full path: if ATR still all-nan → 0.0 without seeding DX from DI.
        # Once ATR has seeded we step DX every bar (including nan DI → carry).
        if not st["rma_tr"]["seeded"]:
            st["value"] = 0.0
            return 0.0

        if self._is_nan_num(atr_v) or self._is_nan_num(pd) or self._is_nan_num(md):
            dx_in: float = math.nan
        else:
            plus_di = 100.0 * float(pd) / float(atr_v) if atr_v else 0.0
            minus_di = 100.0 * float(md) / float(atr_v) if atr_v else 0.0
            denom = plus_di + minus_di
            dx_in = 100.0 * abs(plus_di - minus_di) / denom if denom else 0.0

        adx_v = self._rma_state_step(st["rma_dx"], dx_in, period)
        if self._is_nan_num(adx_v):
            st["value"] = 0.0
            return 0.0
        st["value"] = float(adx_v)
        return float(adx_v)

    def _dmi_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        di_len: int,
        adx_smooth: int,
    ) -> tuple[float, float, float]:
        """Incremental DMI matching BasicIndicators ``_builtin_ta_dmi``.

        +DI/-DI use 0-first DM + RMA(di_len); ADX uses nan-first ``_adx`` path
        with ``adx_smooth`` (separate call-site state via ``_adx_inc_update``).
        """
        if di_len < 1:
            return math.nan, math.nan, math.nan
        slot = self._ta_next_slot()
        key = ("dmi", slot, di_len, adx_smooth)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_h": None,
                "prev_l": None,
                "prev_c": None,
                "rma_tr": self._rma_state_new(),
                "rma_pdm": self._rma_state_new(),
                "rma_mdm": self._rma_state_new(),
                "plus_di": math.nan,
                "minus_di": math.nan,
            }
            bucket[key] = st

        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        prev_h, prev_l, prev_c = st["prev_h"], st["prev_l"], st["prev_c"]
        st["prev_h"], st["prev_l"], st["prev_c"] = h, l, c

        # Bar 0 of series: DM = 0.0 (basic dmi), TR = None
        if prev_h is None or prev_l is None or prev_c is None:
            tr: float | None = None
            plus_dm = 0.0
            minus_dm = 0.0
        else:
            try:
                hf = float(h) if h is not None else 0.0
                lf = float(l) if l is not None else 0.0
                ph = float(prev_h) if prev_h is not None else 0.0
                pl = float(prev_l) if prev_l is not None else 0.0
                pc = float(prev_c)
                tr = max(hf - lf, abs(hf - pc), abs(lf - pc))
                high_diff = hf - ph
                low_diff = pl - lf
                plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0.0
                minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0.0
            except (TypeError, ValueError):
                tr = None
                plus_dm = 0.0
                minus_dm = 0.0

        atr_v = self._rma_state_step(st["rma_tr"], tr, di_len)
        pd = self._rma_state_step(st["rma_pdm"], plus_dm, di_len)
        md = self._rma_state_step(st["rma_mdm"], minus_dm, di_len)

        if self._is_nan_num(atr_v) or self._is_nan_num(pd) or self._is_nan_num(md):
            # Full path: nan atr → 100*pd/atr yields nan when atr is nan (truthy)
            if atr_v is None:
                plus_di = math.nan
                minus_di = math.nan
            elif isinstance(atr_v, float) and math.isnan(atr_v):
                plus_di = math.nan
                minus_di = math.nan
            elif not atr_v:
                plus_di = 0.0
                minus_di = 0.0
            else:
                pd_f = 0.0 if self._is_nan_num(pd) else float(pd)
                md_f = 0.0 if self._is_nan_num(md) else float(md)
                plus_di = 100.0 * pd_f / float(atr_v)
                minus_di = 100.0 * md_f / float(atr_v)
        else:
            if not atr_v:
                plus_di = 0.0
                minus_di = 0.0
            else:
                plus_di = 100.0 * float(pd) / float(atr_v)
                minus_di = 100.0 * float(md) / float(atr_v)

        st["plus_di"] = plus_di
        st["minus_di"] = minus_di

        # ADX: separate call-site (consumes next slot) — same period semantics as full
        adx = self._adx_inc_update(highs, lows, closes, adx_smooth)
        return float(plus_di), float(minus_di), float(adx)

    def _supertrend_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        factor: float,
        atr_period: int,
    ) -> tuple[float, int]:
        """Incremental supertrend matching BasicIndicators simplified path.

        ATR via ``_atr_inc_update`` (own slot); mid/bands/direction O(1).
        """
        atr_val = self._atr_inc_update(highs, lows, closes, atr_period)
        if atr_val is None or not isinstance(atr_val, (int, float)):
            atr_val = 0.0
        try:
            atr_f = float(atr_val)
            if math.isnan(atr_f):
                atr_f = 0.0
        except (TypeError, ValueError):
            atr_f = 0.0

        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        try:
            current_high = float(h) if h is not None else 0.0
            current_low = float(l) if l is not None else 0.0
            current_close = float(c) if c is not None else current_high
        except (TypeError, ValueError):
            current_high = current_low = current_close = 0.0

        mid = (current_high + current_low) / 2.0
        upper = mid + factor * atr_f
        lower = mid - factor * atr_f
        direction = -1 if current_close >= mid else 1
        supertrend = lower if direction < 0 else upper
        return float(supertrend), direction

    def _valuewhen_inc_update(
        self,
        condition: Any,
        source: Any,
        occurrence: int,
    ) -> Any:
        """Incremental ``ta.valuewhen`` — ring of last (occurrence+1) true sources.

        Matches full ``_valuewhen`` when fed one sample per bar.
        """
        if occurrence < 0:
            return None
        slot = self._ta_next_slot()
        key = ("valuewhen", slot, occurrence)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            # Ring of source values at true bars; newest at right.
            st = {"hits": deque(maxlen=occurrence + 1), "value": None}
            bucket[key] = st

        # One sample per bar (list prefixes from unit tests use last element).
        cond = self._series_last(condition) if not isinstance(condition, (bool, int, float)) else condition
        if isinstance(condition, list):
            cond = condition[-1] if condition else None
        src = self._series_last(source)
        if isinstance(source, list):
            src = source[-1] if source else None

        # Match ``if flag`` in full ``_valuewhen``: truthy Python semantics.
        is_true = bool(cond)

        hits: deque[Any] = st["hits"]
        if is_true:
            hits.append(src)
        if len(hits) <= occurrence:
            st["value"] = None
            return None
        # occurrence=0 → most recent; occurrence=1 → second most recent, …
        st["value"] = hits[-(occurrence + 1)]
        return st["value"]

    def _pivothigh_inc_update(
        self,
        series: list[Any],
        left_bars: int,
        right_bars: int,
    ) -> float | None:
        """Incremental pivothigh matching BasicIndicators left-only check."""
        if left_bars < 0 or right_bars < 0:
            return None
        slot = self._ta_next_slot()
        key = ("pivothigh", slot, left_bars, right_bars)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            need = left_bars + 1
            st = {"window": deque(maxlen=max(need, 1)), "n": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        st["window"].append(x)
        st["n"] = int(st["n"]) + 1
        # Full: len(source) <= left + right → None
        if int(st["n"]) <= left_bars + right_bars:
            st["value"] = None
            return None
        window: deque[Any] = st["window"]
        if len(window) < left_bars + 1:
            st["value"] = None
            return None
        current = window[-1]
        if current is None:
            st["value"] = None
            return None
        try:
            cur_f = float(current)
        except (TypeError, ValueError):
            st["value"] = None
            return None
        for i in range(1, left_bars + 1):
            left_val = window[-1 - i]
            if left_val is None:
                continue
            try:
                if float(left_val) >= cur_f:
                    st["value"] = None
                    return None
            except (TypeError, ValueError):
                continue
        st["value"] = cur_f
        return cur_f

    def _pivotlow_inc_update(
        self,
        series: list[Any],
        left_bars: int,
        right_bars: int,
    ) -> float | None:
        """Incremental pivotlow matching BasicIndicators left-only check."""
        if left_bars < 0 or right_bars < 0:
            return None
        slot = self._ta_next_slot()
        key = ("pivotlow", slot, left_bars, right_bars)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            need = left_bars + 1
            st = {"window": deque(maxlen=max(need, 1)), "n": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        st["window"].append(x)
        st["n"] = int(st["n"]) + 1
        if int(st["n"]) <= left_bars + right_bars:
            st["value"] = None
            return None
        window: deque[Any] = st["window"]
        if len(window) < left_bars + 1:
            st["value"] = None
            return None
        current = window[-1]
        if current is None:
            st["value"] = None
            return None
        try:
            cur_f = float(current)
        except (TypeError, ValueError):
            st["value"] = None
            return None
        for i in range(1, left_bars + 1):
            left_val = window[-1 - i]
            if left_val is None:
                continue
            try:
                if float(left_val) <= cur_f:
                    st["value"] = None
                    return None
            except (TypeError, ValueError):
                continue
        st["value"] = cur_f
        return cur_f

    def _dema_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental DEMA: 2*EMA(src) - EMA(EMA(src)). Matches full last value."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("dema", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "ema1": self._ema_state_new(),
                "ema2": self._ema_state_new(),
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        e1 = self._ema_state_step(st["ema1"], x, period)
        e2 = self._ema_state_step(st["ema2"], e1, period)
        if e1 is None or e2 is None:
            st["value"] = None
            return None
        st["value"] = 2.0 * float(e1) - float(e2)
        return st.get("value")

    def _tema_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental TEMA: 3*e1 - 3*e2 + e3. Matches full last value."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("tema", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "ema1": self._ema_state_new(),
                "ema2": self._ema_state_new(),
                "ema3": self._ema_state_new(),
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        e1 = self._ema_state_step(st["ema1"], x, period)
        e2 = self._ema_state_step(st["ema2"], e1, period)
        e3 = self._ema_state_step(st["ema3"], e2, period)
        if e1 is None or e2 is None or e3 is None:
            st["value"] = None
            return None
        st["value"] = 3.0 * float(e1) - 3.0 * float(e2) + float(e3)
        return st.get("value")

    # ------------------------------------------------------------------
    # Round 6 residual: kc / mfi / sar / alma / correlation / percentiles
    # ------------------------------------------------------------------

    def _kc_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        length: int,
        mult: float = 1.0,
    ) -> tuple[float, float, float]:
        """Incremental Keltner Channels matching full ``_builtin_ta_kc``.

        Middle = EMA(close, length); bands = middle ± mult * ATR(length).
        Uses nested ``_ema_inc_update`` + ``_atr_inc_update`` (own slots).
        """
        if length < 1:
            return math.nan, math.nan, math.nan
        middle = self._ema_inc_update(closes, length)
        atr_val = self._atr_inc_update(highs, lows, closes, length)
        if middle is None or (isinstance(middle, float) and math.isnan(middle)):
            return math.nan, math.nan, math.nan
        try:
            mid_f = float(middle)
        except (TypeError, ValueError):
            return math.nan, math.nan, math.nan
        if atr_val is None:
            atr_f = 0.0
        else:
            try:
                atr_f = float(atr_val)
                if math.isnan(atr_f):
                    # Full path: ``atr_val or 0`` is truthy for nan → nan width
                    channel_width = float("nan") * float(mult)
                    return mid_f, mid_f + channel_width, mid_f - channel_width
            except (TypeError, ValueError):
                atr_f = 0.0
        channel_width = atr_f * float(mult)
        return mid_f, mid_f + channel_width, mid_f - channel_width

    def _mfi_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        volumes: list[Any],
        period: int,
    ) -> float:
        """Incremental Money Flow Index matching full ``_mfi`` / ``numba_mfi``.

        Needs ``period + 1`` typical-price samples; returns na until ready.
        Equal TP bars contribute to neither side (reference convention).
        """
        if period < 1:
            return math.nan
        slot = self._ta_next_slot()
        key = ("mfi", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "tps": deque(maxlen=period + 1),
                "mfs": deque(maxlen=period + 1),
                "value": math.nan,
            }
            bucket[key] = st

        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        v = self._series_last(volumes)

        tps: deque[Any] = st["tps"]
        mfs: deque[Any] = st["mfs"]
        if (
            not isinstance(h, (int, float))
            or not isinstance(l, (int, float))
            or not isinstance(c, (int, float))
        ):
            tps.append(None)
            mfs.append(None)
            st["value"] = math.nan
            return math.nan

        vol = float(v) if isinstance(v, (int, float)) else 0.0
        tp = (float(h) + float(l) + float(c)) / 3.0
        tps.append(tp)
        mfs.append(tp * vol)

        if len(tps) <= period:
            st["value"] = math.nan
            return math.nan

        pos = 0.0
        neg = 0.0
        # Last ``period`` money-flow samples (each vs previous TP)
        tp_list = list(tps)
        mf_list = list(mfs)
        for k in range(1, len(tp_list)):
            # only the most recent ``period`` directed samples
            if k < len(tp_list) - period:
                continue
            tp_cur = tp_list[k]
            tp_prev = tp_list[k - 1]
            mf = mf_list[k]
            if tp_cur is None or tp_prev is None or mf is None:
                st["value"] = math.nan
                return math.nan
            if tp_cur > tp_prev:
                pos += float(mf)
            elif tp_cur < tp_prev:
                neg += float(mf)

        if neg == 0.0:
            if pos == 0.0:
                st["value"] = 50.0
                return 50.0
            st["value"] = 100.0
            return 100.0
        ratio = pos / neg
        st["value"] = 100.0 - (100.0 / (1.0 + ratio))
        return float(st["value"])

    def _sar_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        start: float,
        increment: float,
        maximum: float,
    ) -> float | None:
        """Incremental Parabolic SAR matching full ``_sar`` / ``_sar_full`` last value.

        O(1)/bar state machine; skips leading na like the full path.
        """
        slot = self._ta_next_slot()
        key = ("sar", slot, float(start), float(increment), float(maximum))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "started": False,
                "sar": None,
                "ep": None,
                "trend": 1,
                "af": float(start),
                "value": None,
            }
            bucket[key] = st

        h = self._series_last(highs)
        l = self._series_last(lows)

        if not st["started"]:
            if h is None or l is None:
                st["value"] = None
                return None
            try:
                sar0 = float(l)
                ep0 = float(h)
            except (TypeError, ValueError):
                st["value"] = None
                return None
            st["started"] = True
            st["sar"] = sar0
            st["ep"] = ep0
            st["trend"] = 1
            st["af"] = float(start)
            st["value"] = sar0
            return sar0

        previous = st["sar"]
        ep = st["ep"]
        if previous is None or h is None or l is None or ep is None:
            st["value"] = previous
            return previous
        try:
            hi_f, lo_f = float(h), float(l)
            ep_f = float(ep)
            prev_f = float(previous)
        except (TypeError, ValueError):
            st["value"] = previous
            return previous

        trend = int(st["trend"])
        af = float(st["af"])
        if trend == 1:
            sar = prev_f + af * (ep_f - prev_f)
            if hi_f > ep_f:
                ep_f = hi_f
                af = min(af + float(increment), float(maximum))
            if sar > lo_f:
                trend = -1
                sar = ep_f
                ep_f = lo_f
                af = float(start)
        else:
            sar = prev_f - af * (prev_f - ep_f)
            if lo_f < ep_f:
                ep_f = lo_f
                af = min(af + float(increment), float(maximum))
            if sar < hi_f:
                trend = 1
                sar = ep_f
                ep_f = hi_f
                af = float(start)

        st["sar"] = sar
        st["ep"] = ep_f
        st["trend"] = trend
        st["af"] = af
        st["value"] = sar
        return sar

    def _alma_inc_update(
        self,
        series: list[Any],
        length: int,
        offset: float = 0.85,
        sigma: float = 6.0,
    ) -> float | None:
        """Incremental ALMA: O(length) weighted sum over a ring (not O(bars²)).

        Precomputes Gaussian weights once per call-site (length/offset/sigma).
        Matches full ``_builtin_ta_alma`` last value; na in window → None.
        """
        if length <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("alma", slot, length, float(offset), float(sigma))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            m = float(offset) * (length - 1)
            s = length / float(sigma) if sigma else 0.0
            if s == 0.0:
                weights = [1.0] * length
            else:
                weights = [
                    math.exp(-((i - m) ** 2) / (2.0 * s * s)) for i in range(length)
                ]
            wsum = sum(weights)
            st = {
                "window": deque(maxlen=length),
                "weights": weights,
                "wsum": wsum,
                "value": None,
            }
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
        window.append(x)
        if len(window) < length:
            st["value"] = None
            return None
        wsum = float(st["wsum"])
        if wsum == 0.0:
            st["value"] = None
            return None
        total = 0.0
        weights: list[float] = st["weights"]
        for i, v in enumerate(window):
            if v is None:
                st["value"] = None
                return None
            total += float(v) * weights[i]
        st["value"] = total / wsum
        return st.get("value")

    def _correlation_inc_update(
        self,
        source1: list[Any],
        source2: list[Any],
        length: int,
    ) -> float | None:
        """Incremental Pearson correlation matching full ``ta.correlation``.

        Ring of length samples; O(period) recompute over non-na pairs (na-safe).
        Requires ``length`` samples seen (same as full ``len >= length``).
        """
        if length < 2:
            return None
        slot = self._ta_next_slot()
        key = ("correlation", slot, length)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "a": deque(maxlen=length),
                "b": deque(maxlen=length),
                "value": None,
            }
            bucket[key] = st

        raw_a = self._series_last(source1)
        raw_b = self._series_last(source2)
        a_v: float | None
        b_v: float | None
        try:
            a_v = float(raw_a) if raw_a is not None else None
        except (TypeError, ValueError):
            a_v = None
        try:
            b_v = float(raw_b) if raw_b is not None else None
        except (TypeError, ValueError):
            b_v = None
        wa: deque[float | None] = st["a"]
        wb: deque[float | None] = st["b"]
        wa.append(a_v)
        wb.append(b_v)
        if len(wa) < length:
            st["value"] = None
            return None

        pairs = [
            (float(x), float(y))
            for x, y in zip(wa, wb, strict=False)
            if x is not None and y is not None
        ]
        if len(pairs) < 2:
            st["value"] = None
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
        denx = sum((x - mx) ** 2 for x in xs) ** 0.5
        deny = sum((y - my) ** 2 for y in ys) ** 0.5
        if denx == 0 or deny == 0:
            st["value"] = None
            return None
        st["value"] = num / (denx * deny)
        return st.get("value")

    def _percentile_linear_inc_update(
        self,
        series: list[Any],
        period: int,
        percentage: float,
    ) -> float | None:
        """Incremental ``ta.percentile_linear_interpolation`` (O(period) sort)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("pct_lin", slot, period, float(percentage))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": None}
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
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        sorted_w = sorted(v for v in window if v is not None)
        if not sorted_w:
            st["value"] = None
            return None
        n = len(sorted_w)
        if n == 1:
            st["value"] = float(sorted_w[0])
            return st.get("value")
        rank = (float(percentage) / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        st["value"] = float(sorted_w[lo]) * (1.0 - frac) + float(sorted_w[hi]) * frac
        return st.get("value")

    def _percentile_nearest_rank_inc_update(
        self,
        series: list[Any],
        period: int,
        percentage: float,
    ) -> float | None:
        """Incremental ``ta.percentile_nearest_rank`` (O(period) sort)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("pct_nr", slot, period, float(percentage))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=period), "value": None}
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
        window.append(x)
        if len(window) < period:
            st["value"] = None
            return None
        sorted_w = sorted(v for v in window if v is not None)
        if not sorted_w:
            st["value"] = None
            return None
        n = len(sorted_w)
        rank = max(1, int((float(percentage) / 100.0) * n + 0.999999))
        rank = min(rank, n)
        st["value"] = float(sorted_w[rank - 1])
        return st.get("value")

    # ------------------------------------------------------------------
    # Round 7 residual (T2): bb / kama / cmo / stochrsi nested full paths
    # ------------------------------------------------------------------

    def _bb_inc_update(
        self,
        series: list[Any],
        period: int,
        multiplier: float,
    ) -> tuple[float | None, float | None, float | None]:
        """Incremental Bollinger Bands (upper, middle, lower).

        Nested ``_sma_inc_update`` + ``_stdev_inc_update`` (own call-site slots).
        Matches ``_bollinger_bands`` last-value oracle.
        """
        middle = self._sma_inc_update(series, period)
        deviation = self._stdev_inc_update(series, period)
        if middle is None or deviation is None:
            return None, None, None
        try:
            mid_f = float(middle)
            dev_f = float(deviation)
            mult = float(multiplier)
        except (TypeError, ValueError):
            return None, None, None
        return mid_f + dev_f * mult, mid_f, mid_f - dev_f * mult

    def _kama_inc_update(
        self,
        series: list[Any],
        length: int,
        fast: int = 2,
        slow: int = 30,
    ) -> float | None:
        """Incremental Kaufman's AMA matching full ``_builtin_ta_kama`` last value.

        Full path rebuilds the whole KAMA series every bar (O(bars·length)).
        State: price ring (length+1), running sum of |Δ| over ``length`` diffs,
        and the recursive KAMA seed at bar ``length`` (0-based index length-1).
        First non-None output is on bar index ``length`` (need length+1 samples).
        """
        if length < 1:
            return None
        slot = self._ta_next_slot()
        key = ("kama", slot, int(length), int(fast), int(slow))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prices": deque(maxlen=length + 1),
                "diffs": deque(),
                "vol": 0.0,
                "kama": None,
                "seeded": False,
                "bars": 0,
                "value": None,
            }
            bucket[key] = st

        raw = self._series_last(series)
        if raw is None:
            st["value"] = None
            return None
        try:
            x = float(raw)
        except (TypeError, ValueError):
            st["value"] = None
            return None

        prices: deque[float] = st["prices"]
        diffs: deque[float] = st["diffs"]
        prev = prices[-1] if prices else None
        prices.append(x)
        st["bars"] = int(st["bars"]) + 1

        if prev is not None:
            d = abs(x - float(prev))
            if len(diffs) == length:
                st["vol"] = float(st["vol"]) - float(diffs.popleft())
            diffs.append(d)
            st["vol"] = float(st["vol"]) + d

        bars = int(st["bars"])
        if not st["seeded"]:
            if bars < length:
                st["value"] = None
                return None
            # Bar index length-1: seed kama to price; series still all-None.
            st["kama"] = x
            st["seeded"] = True
            st["value"] = None
            return None

        # bars > length → recursive update (matches for i in range(length, n))
        oldest = float(prices[0])
        change = abs(x - oldest)
        volatility = float(st["vol"])
        if volatility != 0.0:
            efficiency = change / volatility
            fastest = 2.0 / (float(fast) + 1.0)
            slowest = 2.0 / (float(slow) + 1.0)
            smoothing = efficiency * (fastest - slowest) + slowest
            sc = smoothing * smoothing
        else:
            sc = (2.0 / (float(slow) + 1.0)) ** 2
        kama = float(st["kama"])
        kama = kama + sc * (x - kama)
        st["kama"] = kama
        st["value"] = kama
        return kama

    def _cmo_inc_update(self, series: list[Any], length: int) -> float | None:
        """Incremental Chande Momentum Oscillator matching full ``ta.cmo``.

        Window of ``length + 1`` samples; up/down sums of signed diffs over
        the window (na pairs skipped). O(length)/bar — avoids full reverse
        materialize via last-sample path.
        """
        if length <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("cmo", slot, int(length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=length + 1), "value": None}
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
        window.append(x)
        if len(window) < length + 1:
            st["value"] = None
            return None

        up = 0.0
        down = 0.0
        prev_v: float | None = None
        for v in window:
            if prev_v is not None and v is not None:
                diff = float(v) - float(prev_v)
                if diff > 0:
                    up += diff
                else:
                    down += -diff
            prev_v = v
        denom = up + down
        if denom == 0.0:
            st["value"] = 0.0
            return 0.0
        st["value"] = 100.0 * (up - down) / denom
        return st.get("value")

    def _stochrsi_inc_update(
        self,
        closes: list[Any],
        rsi_length: int,
        stoch_length: int,
    ) -> dict[str, float | None]:
        """Incremental StochRSI matching AdvancedIndicators full path.

        Full path rebuilds a simple (non-Wilder) RSI series every bar then
        takes max/min over last ``stoch_length`` valid RSI values. Here:
        price ring for one RSI sample O(rsi_length) + RSI ring for stoch.
        Signal: ``0.33 * stochrsi + 0.67 * prev_signal`` (call-site state).
        """
        if rsi_length < 1 or stoch_length < 1:
            return {"stochrsi": None, "signal": None}
        slot = self._ta_next_slot()
        key = ("stochrsi", slot, int(rsi_length), int(stoch_length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prices": deque(maxlen=rsi_length),
                "rsi_ring": deque(maxlen=stoch_length),
                "valid_rsi": 0,
                "signal": None,
                "value": None,
            }
            bucket[key] = st

        raw = self._series_last(closes)
        if raw is None:
            st["value"] = None
            return {"stochrsi": None, "signal": st.get("signal")}
        try:
            x = float(raw)
        except (TypeError, ValueError):
            st["value"] = None
            return {"stochrsi": None, "signal": st.get("signal")}

        prices: deque[float] = st["prices"]
        prices.append(x)
        # Full path: first RSI when bar index >= rsi_length (needs rsi_length+1
        # closes). Price ring of rsi_length is full after rsi_length samples;
        # first RSI is computed on the *next* bar (bars > rsi_length) — match
        # by counting: when len(prices) < rsi_length → still warmup Nones.
        # Full: for i in range(len): if i < rsi_length: None else segment of
        # closes[i-rsi_length+1:i+1] length rsi_length.
        # After rsi_length samples (i=rsi_length-1) still None; after
        # rsi_length+1 samples (i=rsi_length) first RSI on ring of rsi_length.
        # With maxlen=rsi_length ring, after rsi_length appends ring is full
        # at i=rsi_length-1. Full still returns None there. So we need a bar
        # counter: first RSI when bars > rsi_length, using last rsi_length prices.
        bars = int(st.get("bars", 0)) + 1
        st["bars"] = bars

        if bars <= rsi_length:
            # Match full: i < rsi_length → None; at i == rsi_length-1 still None
            st["value"] = None
            return {"stochrsi": None, "signal": None}

        # bars >= rsi_length+1 → prices ring holds closes[i-rsi_length+1:i+1]
        segment = list(prices)
        if len(segment) < rsi_length:
            st["value"] = None
            return {"stochrsi": None, "signal": None}

        gains = 0.0
        losses = 0.0
        for j in range(1, len(segment)):
            d = segment[j] - segment[j - 1]
            if d > 0:
                gains += d
            else:
                losses += -d
        avg_gain = gains / rsi_length
        avg_loss = losses / rsi_length
        if avg_loss != 0:
            rs = avg_gain / avg_loss
        else:
            rs = 100.0
        rsi_val = 100.0 - (100.0 / (1.0 + rs))

        rsi_ring: deque[float] = st["rsi_ring"]
        rsi_ring.append(rsi_val)
        valid = int(st["valid_rsi"]) + 1
        st["valid_rsi"] = valid
        if valid < stoch_length or len(rsi_ring) < stoch_length:
            st["value"] = None
            return {"stochrsi": None, "signal": None}

        rsi_high = max(rsi_ring)
        rsi_low = min(rsi_ring)
        rsi_range = rsi_high - rsi_low
        if rsi_range == 0.0:
            stochrsi_val = 0.0
        else:
            stochrsi_val = (rsi_val - rsi_low) / rsi_range * 100.0

        prev_sig = st.get("signal")
        if prev_sig is None:
            prev_sig = stochrsi_val
        signal = stochrsi_val * 0.33 + float(prev_sig) * 0.67
        st["signal"] = signal
        st["value"] = stochrsi_val
        return {"stochrsi": stochrsi_val, "signal": signal}

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

    def _last_sample_path(self) -> bool:
        """True when pure-incremental kernels may skip full series materialization.

        Mirrors ``PYNE_TA_INCREMENTAL`` / ``_use_incremental_ta``: bar mode with
        call-site state only needs one sample via ``_series_last``.
        """
        return self._use_incremental_ta()

    def _as_series_or_raw(self, value: Any, *, last_sample_ok: bool = False) -> Any:
        """Materialize chronological list, or pass *value* through for inc kernels.

        When ``last_sample_ok`` and incremental TA is active, return *value*
        unchanged so ``_series_last`` can read ``.current`` / ``history[0]`` /
        ``list[-1]`` without reversing PineSeries history every bar.
        """
        if last_sample_ok and self._last_sample_path():
            return value
        return self._as_series(value)

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

        **Performance (interpret / bar mode):**
        - Same-bar cache keyed by ``id(value)`` + length + head sample so
          multiple ``ta.*`` calls on the same ``PineSeries`` reverse once.
        - Only the newest ``_SERIES_MAX`` samples are reversed (no full-history
          reverse then slice).
        - Pure-incremental kernels only need the last sample; prefer
          ``_as_series_or_raw(..., last_sample_ok=True)`` or
          ``_expect_series(..., last_sample_ok=True)`` so PineSeries is never
          reversed on the hot path.
        """
        if isinstance(value, list):
            return self._cap_series_list(value)
        # Duck-type PineSeries: newest-first history (deque or list)
        hist = getattr(value, "history", None)
        if hist is not None:
            try:
                n = len(hist)
            except TypeError:
                n = -1
            if n == 0:
                cur = getattr(value, "current", None)
                return [cur] if cur is not None else []
            if n > 0:
                cap = self._SERIES_MAX
                take = n if n <= cap else cap
                # Same-bar cache: many ta.* calls share one PineSeries per bar.
                head = hist[0]
                cache = getattr(self, "_pine_as_series_cache", None)
                if cache is None:
                    cache = {}
                    self._pine_as_series_cache = cache  # type: ignore[attr-defined]
                key = id(value)
                ent = cache.get(key)
                if ent is not None and ent[0] == n and ent[1] is head and ent[2] == take:
                    return ent[3]
                # Newest-first → take first `take` then reverse to chronological.
                # Avoid list(reversed(full_history)) when n >> SERIES_MAX.
                if take == n:
                    raw = list(reversed(hist))
                else:
                    # hist[0] newest … hist[take-1] oldest among window
                    raw = [hist[i] for i in range(take - 1, -1, -1)]
                cache[key] = (n, head, take, raw)
                return raw
        # Named series reference — look up from the pre-loaded dict
        series_map = getattr(self, "current_series", None) or {}
        if isinstance(value, str):
            if value in series_map:
                src = series_map[value]
                # Prefer view/cap without full copy when already a list
                if isinstance(src, list):
                    return self._cap_series_list(src)
                return list(src)
            # Bare TA series aliases that slipped through as name strings
            # (``ema(obv, 14)`` when visit_Name / arg plan did not resolve).
            try:
                from pynescript.ast.evaluator.names import _BARE_TA_SERIES
            except Exception:  # pragma: no cover - import always available in package
                _BARE_TA_SERIES = frozenset()
            if (
                value in _BARE_TA_SERIES
                and hasattr(self, "_is_registered_builtin")
                and hasattr(self, "_call_builtin")
                and self._is_registered_builtin(value)
            ):
                try:
                    result = self._call_builtin(value, [])
                except Exception:
                    result = None
                if isinstance(result, list):
                    return self._cap_series_list(result)
                if result is None:
                    return []
                return [result]
            # Numeric strings → single sample; other strings soft-fail to empty
            # (avoids ``float('obv')`` / ``float('#2962FF')`` hard crashes).
            try:
                return [float(value)]
            except (TypeError, ValueError):
                return []
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

    def _context_source(self, name: str) -> Any:
        """Raw context series for last-sample kernels (no cap-slice copy).

        Runtime stores chronological append-only lists in ``current_series``.
        Incremental kernels only read ``_series_last``; return the live list
        (or empty) without allocating a capped slice.
        """
        series_map = getattr(self, "current_series", None) or {}
        src = series_map.get(name)
        if src is None:
            return []
        return src

    def _is_period_like(self, value: Any) -> bool:
        """True if *value* looks like a length/period (int or whole float).

        Accepts series last-samples of whole floats so ``ta.highest(14.0)`` and
        list periods work the same as bare ints.
        """
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float) and value == int(value):
            return True
        # Series / list last sample of a period-like scalar
        if type(value) is list and value:
            return self._is_period_like(value[-1])
        if type(value) is tuple and value:
            return self._is_period_like(value[-1])
        if not isinstance(value, (list, tuple, str, bytes)) and hasattr(value, "current"):
            cur = getattr(value, "current", None)
            if cur is not None and cur is not value:
                return self._is_period_like(cur)
        return False

    def _expect_period(self, value: Any, message: str) -> int:
        """Coerce TA length/period; ``na`` → ``0`` so kernels return na (reference-like).

        Non-na invalid types still raise via :func:`pine_period_or_none`.
        Period ``<= 0`` is treated as invalid length by SMA/EMA/… kernels.
        """
        period = pine_period_or_none(value, message, self._error)
        if period is None:
            return 0
        return period

    def _expect_series(
        self,
        args: list[Any],
        length: int,
        *,
        default_source: str | None = "close",
        allow_period_only: bool = False,
        last_sample_ok: bool = False,
    ) -> tuple[Any, int]:
        """Validate and extract series and period arguments.

        reference Pine allows ``ta.sma(close, 14)`` and, for some functions,
        ``ta.highest(14)`` (period-only, source defaults to high/low/close).

        When ``allow_period_only`` is True and a single period-like arg is
        passed, the series is taken from ``current_series[default_source]``.

        Float / series-like lengths coerce via :meth:`_expect_period` (near-
        integer floats → int; ``na`` → period ``0`` / na result).

        **last_sample_ok:** when True *and* incremental TA is active, skip
        chronological materialization of PineSeries / history wrappers.
        The returned source is raw (list, PineSeries, scalar) and is only safe
        for kernels that use ``_series_last`` (pure incremental update paths).
        Full-recompute paths must leave this False (default).
        """
        n = len(args)
        # Soft-ignore trailing extras (linter signature demos: ta.sma(close, 14, extra))
        if n > length >= 1:
            args = args[:length]
            n = length
        # Hot path: (series, period) with plain int period + last-sample inc
        if n == length and length == BINARY:
            period_raw = args[1]
            if type(period_raw) is int:
                period = period_raw
            else:
                period = self._expect_period(
                    period_raw,
                    "Second argument must be an integer (period)",
                )
            if last_sample_ok and self._use_incremental_ta():
                return args[0], period
            return self._as_series(args[0]), period

        raw_ok = bool(last_sample_ok) and self._use_incremental_ta()
        if allow_period_only and n == 1 and self._is_period_like(args[0]):
            if not default_source:
                self._error(f"ta.* function requires {length} argument(s), got 1. Expected: (series, period)")
            period = self._expect_period(args[0], "Period must be an integer")
            if raw_ok:
                return self._context_source(default_source), period
            series = self._context_series(default_source)
            return series, period
        if n != length:
            self._error(f"ta.* function requires {length} argument(s), got {n}. Expected: (series, period)")
        # Period first so invalid periods fail before any materialization work.
        period = self._expect_period(
            args[1] if length > 1 else args[0],
            "Second argument must be an integer (period)" if length > 1 else "Period must be an integer",
        )
        if raw_ok:
            return args[0], period
        series = self._as_series(args[0])
        return series, period

    def _expect_two_series(
        self,
        args: list[Any],
        *,
        last_sample_ok: bool = False,
    ) -> tuple[Any, Any]:
        """Validate and extract two series arguments.

        With ``last_sample_ok`` + incremental TA, pass sources through for
        stateful crossover / last-sample kernels (no PineSeries reverse).
        """
        if len(args) != BINARY:
            self._error("Function takes two series arguments")
        if last_sample_ok and self._use_incremental_ta():
            return args[0], args[1]
        return (
            self._as_series(args[0]),
            self._as_series(args[1]),
        )

    def _expect_int(self, value: Any, message: str) -> int:
        """Validate / coerce period-like values (delegates to shared helper).

        Kept on TechnicalHelpers so submodule unit tests that only mix this
        class still resolve ``_expect_int``. Full Runtime evaluator prefers
        :meth:`BuiltinDispatchMixin._expect_int` via MRO (same implementation).
        """
        return pine_expect_int(value, message, self._error)

    def _expect_number(self, value: Any, message: str) -> float:
        """Validate that value is numeric and return as float."""
        # Fast path
        t = type(value)
        if t is float:
            return value
        if t is int:
            return float(value)
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes, int, float)):
            value = value.current
            t = type(value)
            if t is float:
                return value
            if t is int:
                return float(value)
        if t is list and value:
            value = value[-1]
            t = type(value)
            if t is float:
                return value
            if t is int:
                return float(value)
        if value is None:
            self._error(f"{message}. Got: na")
        if not isinstance(value, int | float) or isinstance(value, bool):
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
        """Simple Moving Average.

        Strict window (match compile ``numba_sma`` / reference Pine): any ``na`` in
        the last ``period`` samples yields ``na``; average divides by ``period``.
        """
        result: list[float | None] = []
        if not series or period <= 0:
            return result
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            if any(value is None for value in window):
                result.append(None)
                continue
            try:
                result.append(sum(float(v) for v in window) / period)
            except (TypeError, ValueError):
                result.append(None)
        return result

    def _ema(self, series: list[Any], period: int) -> list[float | None]:
        """Exponential Moving Average (SMA seed).

        Dual-host aligned with ``_ema_inc_update`` / ``numba_ema`` / reference Pine:
        seed = mean of the first ``period`` finite samples (``na`` until the
        window is full), then ``alpha * x + (1-alpha) * ema`` with
        ``alpha = 2/(period+1)``. Missing samples after seed hold the previous
        EMA (interpret convention).
        """
        if not series or period <= 0:
            return [None] * len(series)
        alpha = 2.0 / (period + 1)
        ema_values: list[float | None] = []
        seed_buf: list[float] = []
        seeded = False
        ema: float | None = None
        for raw in series:
            x: Any = raw
            if x is not None and type(x) is not float and type(x) is not int:
                try:
                    x = float(x)
                except (TypeError, ValueError):
                    x = None
            if not seeded:
                if x is None:
                    ema_values.append(None)
                    continue
                seed_buf.append(float(x))
                if len(seed_buf) < period:
                    ema_values.append(None)
                    continue
                ema = sum(seed_buf[:period]) / period
                seeded = True
                seed_buf = []
                ema_values.append(ema)
                continue
            if x is None:
                ema_values.append(ema)
                continue
            ema = alpha * float(x) + (1.0 - alpha) * float(ema)
            ema_values.append(ema)
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
        """Weighted Moving Average — full window of non-``na`` required (reference Pine / compile)."""
        if period <= 0 or len(series) < period:
            return None
        window = series[-period:]
        if any(v is None for v in window):
            return None
        total = period * (period + 1) / 2.0
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
        """Standard deviation over period (strict window, match compile/reference Pine).

        Any ``na`` in the last ``period`` samples yields ``na``; sample stdev
        (ddof=1) divides by ``period - 1`` over the full window.
        """
        if period <= 1 or len(series) < period:
            return None
        window = series[-period:]
        vals: list[float] = []
        for v in window:
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:  # NaN
                return None
            vals.append(fv)
        return statistics.stdev(vals)

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

    @staticmethod
    def _cmp_le(a: Any, b: Any) -> bool | None:
        """``a <= b`` with Pine na (None) → None (never raises)."""
        if a is None or b is None:
            return None
        try:
            return float(a) <= float(b)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cmp_ge(a: Any, b: Any) -> bool | None:
        """``a >= b`` with Pine na (None) → None (never raises)."""
        if a is None or b is None:
            return None
        try:
            return float(a) >= float(b)
        except (TypeError, ValueError):
            return None

    def _crossover(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses above series2 (na-safe).

        reference / numba / bar-mode stateful: previous bar was ``s1 <= s2`` and
        current is strictly ``s1 > s2``. Any na operand → False (no cross).
        """
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_le(series1[-2], series2[-2])
        curr = self._cmp_gt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _crossunder(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses below series2 (na-safe).

        Previous ``s1 >= s2`` and current strictly ``s1 < s2``. na → False.
        """
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_ge(series1[-2], series2[-2])
        curr = self._cmp_lt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _cross_stateful(
        self,
        series1: list[Any],
        series2: list[Any],
        *,
        under: bool,
        either: bool = False,
    ) -> bool:
        """Bar-mode crossover when sources are last-sample only (or short lists).

        Runtime sets ``_cross_call_i = 0`` each bar and keeps ``_cross_state``
        across bars: map call-index → previous (s1, s2) pair.

        Uses ``_series_last`` so PineSeries / scalars / lists work without
        materializing history. Comparison matches full-series ``_crossover`` /
        ``_crossunder``: previous ``s1 <= s2`` (over) / ``s1 >= s2`` (under)
        and current strictly the other side.

        When *either* is True (``ta.cross``), one call-site slot detects either
        direction without double-advancing ``_cross_call_i``.
        """
        a = self._series_last(series1)
        b = self._series_last(series2)
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
                # Match list-path: prev <= / >= , curr strict
                over = pa <= pb and a_f > b_f
                under_hit = pa >= pb and a_f < b_f
                if either:
                    result = over or under_hit
                elif under:
                    result = under_hit
                else:
                    result = over
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
        """Check if series is falling for period (na-safe).

        Strict consecutive decline: ``s[-1] < s[-2] < ...`` over ``period`` bars.
        Any Pine na (None) or non-numeric sample → False (never TypeError).
        """
        if len(series) < period or period < 1:
            return False
        for idx in range(1, period):
            # consecutive: series[-idx] < series[-idx-1] for falling
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
        """Check if series is rising for period (na-safe).

        Strict consecutive rise; any na / non-numeric → False (never TypeError).
        """
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
        """Offset to highest value in period (na-safe; matches ``_highestbars_inc_update``).

        Returns bars-back offset of the extreme (0 = current bar is highest).
        Skips None / non-numeric; all-na or short window → ``-1``.
        On ties prefers the **oldest** extreme in the window (leftmost).
        """
        if period < 1 or len(series) < period:
            return -1
        window = series[-period:]
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best_v is None or fv > best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            return -1
        return -(period - 1 - best_i)

    def _lowestbars(self, series: list[float], period: int) -> int:
        """Offset to lowest value in period (na-safe; matches ``_lowestbars_inc_update``).

        Same na / non-numeric / all-na contract as :meth:`_highestbars`.
        """
        if period < 1 or len(series) < period:
            return -1
        window = series[-period:]
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if best_v is None or fv < best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            return -1
        return -(period - 1 - best_i)

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
