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
from collections.abc import Sequence
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
        try:
            cached = self._pine_ta_inc_cached
        except AttributeError:
            cached = None
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
        """Per-bar call-site index (reset by Runtime each bar, like crossover).

        Slot identity is call *order*, not the ``ta.`` prefix. Host must
        zero ``_ta_call_i`` on every bar, including v4 bare ``sma``/``wma``.
        """
        try:
            i = self._ta_call_i
        except AttributeError:
            i = 0
        if type(i) is not int:
            i = int(i or 0)
        self._ta_call_i = i + 1  # type: ignore[attr-defined]
        return i

    def _ta_state_bucket(self) -> dict[tuple[Any, ...], dict[str, Any]]:
        try:
            state = self._ta_inc_state
        except AttributeError:
            state = None
        if state is None:
            state = {}
            self._ta_inc_state = state  # type: ignore[attr-defined]
        return state

    def _ta_key1(self, kind: str, period: int) -> tuple[dict[tuple[Any, ...], dict[str, Any]], tuple[Any, ...]]:
        """Advance the call-site slot and return ``(bucket, key)``.

        ``key`` is ``(kind, slot, period)``. The tuple is reused across bars
        when that signature stays put, so the dict lookup keeps its cached
        hash. A period change, or a realtime rollback that restored a
        different signature, allocates a fresh key and looks that up.
        Slot order matches :meth:`_ta_next_slot` (one increment per call).
        """
        try:
            i = self._ta_call_i
        except AttributeError:
            i = 0
        if type(i) is not int:
            i = int(i or 0)
        self._ta_call_i = i + 1  # type: ignore[attr-defined]
        try:
            bucket = self._ta_inc_state
        except AttributeError:
            bucket = None
        if bucket is None:
            bucket = {}
            self._ta_inc_state = bucket  # type: ignore[attr-defined]
        try:
            cache = self._ta_key_cache
        except AttributeError:
            cache = []
            self._ta_key_cache = cache  # type: ignore[attr-defined]
        if cache is None:
            cache = []
            self._ta_key_cache = cache  # type: ignore[attr-defined]
        key: tuple[Any, ...] | None = cache[i] if i < len(cache) else None
        if key is not None and key[0] == kind and key[1] == i and len(key) == 3 and key[2] == period:
            return bucket, key
        key = (kind, i, period)
        ncache = len(cache)
        if i == ncache:
            cache.append(key)
        elif i < ncache:
            cache[i] = key
        else:
            cache.extend([None] * (i - ncache))
            cache.append(key)
        return bucket, key

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
        # PineSeries / RingPineSeries store the bar sample on ``.current``.
        # LOAD_ATTR beats getattr() on the TA hot path; objects without the
        # attribute fall through to history / sequence.
        try:
            return series.current  # type: ignore[attr-defined]
        except AttributeError:
            pass
        hist = getattr(series, "history", None)
        if hist is not None:
            try:
                if len(hist) == 0:
                    return None
                # Newest-first (PineSeries deque) → index 0 is current bar
                return hist[0]
            except TypeError:
                pass
        # ChronoTailView / other oldest-first sequences (no .current)
        if isinstance(series, Sequence) and not isinstance(series, (str, bytes)):
            try:
                return series[-1] if len(series) else None
            except TypeError:
                pass
        return series

    @staticmethod
    def _finite_or_none(x: Any) -> float | None:
        """Coerce a sample to finite float; ``None`` / NaN / non-numeric → None."""
        if x is None:
            return None
        t = type(x)
        if t is float:
            return None if x != x else x
        if t is int or t is bool:
            return float(x)
        try:
            xf = float(x)
        except (TypeError, ValueError):
            return None
        return None if xf != xf else xf

    def _sma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental SMA matching full ``_sma`` NA-window rules (last value).

        One sample per call-site per bar (``series[-1]``). Does not depend on
        full series length — safe with ``_SERIES_MAX`` truncation.

        Maintains a running sum/count of non-None samples for O(1) updates.
        """
        if period <= 0:
            return None
        bucket, key = self._ta_key1("sma", period)
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "count": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        if len(window) == period:
            old = window.popleft()
            of = self._finite_or_none(old)
            if of is not None:
                st["sum"] -= of
                st["count"] -= 1
        xf = self._finite_or_none(x)
        window.append(xf)
        if xf is not None:
            st["sum"] += xf
            st["count"] += 1
        # Strict window (match compile numba_sma / reference Pine): any na in the length
        # window → na. Require count == period (every slot finite). IEEE NaN
        # (e.g. ta.rci warmup) is na — never add NaN to the running sum (poison).
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

        Seed = SMA of the first ``period`` *consecutive* finite samples
        (``numba_ema_inc``). A na/NaN before the seed is ready resets the
        seed buffer so interleaved 0/na sources (RVI ternary) do not seed
        early. Prior first-value seed diverged from compile on Chaikin Osc etc.
        """
        if period <= 0:
            return None
        bucket, key = self._ta_key1("ema", period)
        st = bucket.get(key)
        if st is None:
            st = {
                "ema": None,
                "seeded": False,
                "seed_buf": [],
                "value": None,
            }
            bucket[key] = st
        x = self._finite_or_none(self._series_last(series))
        alpha = 2.0 / (period + 1)
        if not st["seeded"]:
            if x is None:
                # Consecutive window: na breaks the SMA seed (match compile).
                st["seed_buf"] = []
                st["value"] = None
                return None
            st["seed_buf"].append(x)
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
            st["ema"] = x
        else:
            st["ema"] = alpha * x + (1.0 - alpha) * float(prev)
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
        bucket, key = self._ta_key1("rsi", period)
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
    ) -> tuple[float | None, float | None, float | None]:
        """Incremental MACD matching full ``_macd`` (last macd/signal/hist).

        Uses one call-site slot with three internal EMA states (fast/slow/signal).
        """
        if fast <= 0 or slow <= 0 or signal <= 0:
            return None, None, None
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
        last_macd = None if macd_val is None else float(macd_val)
        last_signal = None if sig_val is None else float(sig_val)
        if macd_val is not None and sig_val is not None:
            last_hist = float(macd_val) - float(sig_val)
        else:
            last_hist = None
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
        bucket, key = self._ta_key1("atr", period)
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_close": None,
                "started": False,
                "rma": self._rma_state_new(),
                "value": None,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        if not st["started"]:
            st["started"] = True
            st["prev_close"] = c
            if h is None or l is None:
                st["value"] = None
                return None
            try:
                tr = float(h) - float(l)
            except (TypeError, ValueError):
                st["value"] = None
                return None
            st["value"] = self._rma_state_step(st["rma"], tr, period)
            return st.get("value")
        prev_c = st["prev_close"]
        st["prev_close"] = c
        if prev_c is None or h is None or l is None or c is None:
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

    def _atr_normalized_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
    ) -> float | None:
        """Incremental ATR as a percent of close matching full ``ta.atr_normalized``.

        Always steps ``_atr_inc_update`` (one slot) including warmup / na /
        zero close so later bars stay aligned. ``close == 0`` or non-finite
        close → na.
        """
        atr_val = self._atr_inc_update(highs, lows, closes, period)
        c = self._finite_or_none(self._series_last(closes))
        if c is None or c == 0.0:
            return None
        if atr_val is None:
            return None
        try:
            af = float(atr_val)
        except (TypeError, ValueError):
            return None
        if af != af:
            return None
        return (af / c) * 100.0

    def _stdev_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental population stdev matching full ``_stdev`` (last value).

        Strict window (match compile ``numba_stdev`` / reference / ``_sma``): any ``na``
        in the length window yields ``na``. Reference ``ta.stdev`` uses ddof=0
        over the full ``period`` finite samples (requires ``period >= 2``).
        """
        if period <= 1:
            return None
        bucket, key = self._ta_key1("stdev", period)
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
        # population variance: (sumsq - sum^2/n) / n
        s = float(st["sum"])
        ss = float(st["sumsq"])
        var = (ss - (s * s) / n) / n
        # floating-point cancellation guard
        var = max(var, 0.0)
        st["value"] = math.sqrt(var)
        return st.get("value")

    def _highest_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental highest matching full ``_highest`` (last value).

        Monotonic-deque sliding maximum: amortized O(1) per bar instead of
        the former O(period) scan (``ta.highest(high, 200)`` x 50k bars was
        10M comparisons per call site). na / non-numeric samples are skipped
        (they poison nothing), matching the previous scan semantics.
        """
        if period <= 0:
            return None
        bucket, key = self._ta_key1("highest", period)
        st = bucket.get(key)
        if st is None:
            st = {"dq": deque(), "count": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        dq: deque[Any] = st["dq"]
        st["count"] += 1
        seq = st["count"]
        fv: float | None = None
        if x is not None:
            try:
                fv = float(x)
            except (TypeError, ValueError):
                fv = None
            if fv is not None and fv != fv:  # NaN
                fv = None
        if fv is not None:
            # Drop dominated records (ties included — equal values are
            # interchangeable for max semantics); keep the newest.
            while dq and dq[-1][1] <= fv:
                dq.pop()
            dq.append((seq, fv))
        # Evict records that fell out of the period window.
        min_seq = seq - period + 1
        while dq and dq[0][0] < min_seq:
            dq.popleft()
        if seq < period:
            st["value"] = None
            return None
        best = dq[0][1] if dq else None
        st["value"] = best
        return best

    def _lowest_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental lowest matching full ``_lowest`` (last value).

        Monotonic-deque sliding minimum (see :meth:`_highest_inc_update`).
        """
        if period <= 0:
            return None
        bucket, key = self._ta_key1("lowest", period)
        st = bucket.get(key)
        if st is None:
            st = {"dq": deque(), "count": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        dq: deque[Any] = st["dq"]
        st["count"] += 1
        seq = st["count"]
        fv: float | None = None
        if x is not None:
            try:
                fv = float(x)
            except (TypeError, ValueError):
                fv = None
            if fv is not None and fv != fv:  # NaN
                fv = None
        if fv is not None:
            while dq and dq[-1][1] >= fv:
                dq.pop()
            dq.append((seq, fv))
        min_seq = seq - period + 1
        while dq and dq[0][0] < min_seq:
            dq.popleft()
        if seq < period:
            st["value"] = None
            return None
        best = dq[0][1] if dq else None
        st["value"] = best
        return best

    @staticmethod
    def _wma_state_new() -> dict[str, Any]:
        return {
            "window": deque(),
            "sum": 0.0,
            "wsum": 0.0,
            "na_count": 0,
            "steps": 0,
            "dirty": True,
            "value": None,
        }

    @staticmethod
    def _wma_parse_sample(raw: Any) -> float | None:
        """None / non-numeric / NaN → None (Pine na)."""
        if raw is None:
            return None
        try:
            x = float(raw)
        except (TypeError, ValueError):
            return None
        if x != x:
            return None
        return x

    @staticmethod
    def _wma_recompute_window(window: deque[Any] | list[Any], period: int) -> tuple[float, float] | None:
        """``(sum, weighted_sum)`` for a full finite window; None if any na."""
        if period <= 0 or len(window) < period:
            return None
        s = 0.0
        ws = 0.0
        for i, v in enumerate(window):
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:
                return None
            s += fv
            ws += fv * (i + 1)
        return s, ws

    @staticmethod
    def _wma_state_step(st: dict[str, Any], raw: Any, period: int) -> float | None:
        """One WMA sample. O(1) when the window is all-finite.

        Oldest weight 1 … newest weight ``period``. Strict window: any na → na.
        Reseeds from the ring every ``period`` steps to bound float drift.
        """
        if period <= 0:
            st["value"] = None
            return None
        x = TechnicalHelpers._wma_parse_sample(raw)
        window: deque[Any] = st["window"]
        old: Any = None
        popped = False
        if len(window) == period:
            old = window.popleft()
            popped = True
            if old is None:
                st["na_count"] = int(st["na_count"]) - 1
        window.append(x)
        if x is None:
            st["na_count"] = int(st["na_count"]) + 1
        st["steps"] = int(st["steps"]) + 1
        if len(window) < period or int(st["na_count"]) > 0:
            st["dirty"] = True
            st["value"] = None
            return None
        reseed = bool(st["dirty"]) or not popped or old is None or (int(st["steps"]) % period == 0)
        if reseed:
            recomputed = TechnicalHelpers._wma_recompute_window(window, period)
            if recomputed is None:
                st["dirty"] = True
                st["value"] = None
                return None
            st["sum"], st["wsum"] = recomputed
            st["dirty"] = False
        else:
            new = float(x)
            st["wsum"] = float(st["wsum"]) - float(st["sum"]) + new * period
            st["sum"] = float(st["sum"]) - float(old) + new
        st["value"] = float(st["wsum"]) / (period * (period + 1) / 2.0)
        return st.get("value")

    def _wma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental WMA matching full ``_wma`` / compile ``numba_wma``.

        O(1) running sum + weighted sum (oldest weight 1). Strict window:
        any na in the period → na (do not drop-na and reweight).
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("wma", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = self._wma_state_new()
            bucket[key] = st
        return self._wma_state_step(st, self._series_last(series), period)

    def _sma_weighted_inc_update(
        self,
        series: list[Any],
        period: int,
        weight_type: str = "linear",
    ) -> float | None:
        """Incremental weighted SMA matching full ``ta.sma_weighted`` last window.

        Weights: linear ``1..n`` (default), quadratic ``(i+1)**2``, sqrt
        ``(i+1)**0.5``. Short window or any non-numeric slot → None (same as
        ``len(valid_data) < period``). One slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        if not isinstance(weight_type, str):
            weight_type = "linear"
        slot = self._ta_next_slot()
        if n < 1:
            return None
        key = ("sma_weighted", slot, n, weight_type)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            if weight_type == "quadratic":
                weights = [(i + 1) ** 2 for i in range(n)]
            elif weight_type == "sqrt":
                weights = [(i + 1) ** 0.5 for i in range(n)]
            else:
                weights = [i + 1 for i in range(n)]
            wsum = float(sum(weights))
            st = {
                "window": deque(maxlen=n),
                "weights": weights,
                "wsum": wsum,
                "value": None,
            }
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None = float(raw) if isinstance(raw, (int, float)) else None
        window: deque[float | None] = st["window"]
        window.append(x)
        if len(window) < n:
            st["value"] = None
            return None
        if any(v is None for v in window):
            st["value"] = None
            return None
        wsum = float(st["wsum"])
        if wsum <= 0.0:
            st["value"] = None
            return None
        weights: list[float] = st["weights"]
        total = 0.0
        for i, v in enumerate(window):
            total += float(v) * weights[i]
        st["value"] = total / wsum
        return st.get("value")

    def _tr_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        handle_na: bool = False,
    ) -> float | None:
        """Incremental True Range last value (matches ``_tr`` bar-mode finalize).

        ``handle_na=True`` seeds bar 0 with ``high - low`` (``ta.tr(true)``);
        the default leaves bar 0 as ``na``.
        """
        slot = self._ta_next_slot()
        key = ("tr", slot, bool(handle_na))
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
            st["started"] = True
            if handle_na and h is not None and l is not None:
                try:
                    st["value"] = float(h) - float(l)
                except (TypeError, ValueError):
                    st["value"] = None
                return st.get("value")
            # Default: no TR on bar 0 (matches full ``_tr`` result[0] = None)
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

    def _extreme_window_push(self, st: dict[str, Any], x: Any, period: int, *, mode: str) -> float | None:
        """Maintain a monotonic-deque sliding extreme (amortized O(1)/bar).

        State (``st``): ``dq`` of ``(seq, value)`` records (dominated entries
        popped), ``bad`` seq list of invalid (na/non-numeric) samples,
        ``count`` total samples seen, ``na_count`` invalid samples currently
        in the period window. Returns the window extreme once the window is
        full and na-free; ``None`` while warming up or when any sample in the
        window is invalid (na poisons the window — callers decide na policy).
        """
        dq: deque[Any] = st["dq"]
        bad: deque[Any] = st["bad"]
        st["count"] += 1
        seq = int(st["count"])
        fv: float | None = None
        if x is not None:
            try:
                fv = float(x)
            except (TypeError, ValueError):
                fv = None
            if fv is not None and fv != fv:  # NaN
                fv = None
        if fv is None:
            st["na_count"] += 1
            bad.append(seq)
        elif mode == "high":
            while dq and dq[-1][1] <= fv:
                dq.pop()
            dq.append((seq, fv))
        else:
            while dq and dq[-1][1] >= fv:
                dq.pop()
            dq.append((seq, fv))
        # One sample leaves per bar once the window is full: the dropped
        # sample is seq - period (the window covers [seq-period+1, seq]).
        min_seq = seq - period + 1
        if seq > period:
            dropped = seq - period
            if bad and bad[0] == dropped:
                bad.popleft()
                st["na_count"] -= 1
        while dq and dq[0][0] < min_seq:
            dq.popleft()
        if seq < period or st["na_count"] > 0:
            return None
        return dq[0][1] if dq else None

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
                "h": {"dq": deque(), "bad": deque(), "count": 0, "na_count": 0},
                "l": {"dq": deque(), "bad": deque(), "count": 0, "na_count": 0},
                "value": None,
            }
            bucket[key] = st
        c = self._finite_or_none(self._series_last(source))
        h = self._series_last(highs)
        l = self._series_last(lows)
        # Monotonic-deque extremes (amortized O(1)); na anywhere → na
        # (matches full ``length`` window requirement / numba_stoch_inc).
        hh = self._extreme_window_push(st["h"], h, length, mode="high")
        ll = self._extreme_window_push(st["l"], l, length, mode="low")
        if hh is None or ll is None or c is None:
            st["value"] = None
            return None
        if hh == ll:
            st["value"] = 50.0
            return 50.0
        st["value"] = 100.0 * (c - ll) / (hh - ll)
        return st.get("value")

    def _stoch_smooth_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
        smooth_k: int,
        smooth_d: int,
    ) -> float | None:
        """Incremental smoothed stochastic matching full ``ta.stoch_smooth``.

        Raw stoch over last ``period`` bars (partial window while warming up;
        na if any high/low/close in the window is non-numeric), then
        ``EMA(stoch, smooth_k)`` then ``EMA(that, smooth_d)`` via SMA-seed
        EMA state (same as full ``_ema``). One call-site slot every bar,
        including warmup / na.
        """
        slot = self._ta_next_slot()
        n = int(period)
        sk = int(smooth_k)
        sd = int(smooth_d)
        if n < 1 or sk < 1 or sd < 1:
            return None
        key = ("stoch_smooth", slot, n, sk, sd)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h": deque(maxlen=n),
                "l": deque(maxlen=n),
                "ema_k": self._ema_state_new(),
                "ema_d": self._ema_state_new(),
                "value": None,
            }
            bucket[key] = st
        h = self._finite_or_none(self._series_last(highs))
        l = self._finite_or_none(self._series_last(lows))
        c = self._finite_or_none(self._series_last(closes))
        hw: deque[float | None] = st["h"]
        lw: deque[float | None] = st["l"]
        hw.append(h)
        lw.append(l)
        stoch: float | None = None
        if c is not None and not any(v is None for v in hw) and not any(v is None for v in lw):
            hh = max(hw)
            ll = min(lw)
            if hh == ll:
                stoch = 50.0
            else:
                stoch = 100.0 * (c - ll) / (hh - ll)
        k_val = self._ema_state_step(st["ema_k"], stoch, sk)
        d_val = self._ema_state_step(st["ema_d"], k_val, sd)
        st["value"] = d_val
        return d_val

    def _rsi_divergence_inc_update(
        self,
        series: list[Any],
        period: int,
    ) -> float:
        """Incremental RSI divergence matching full ``ta.rsi_divergence``.

        Last-(period+1) min/max scaled to [-1, 1]:
        ``(rsi - min) / (max - min) * 2 - 1``. 0.0 while ``i < period``, when
        fewer than 2 numeric values are in the window, when the current sample
        is non-numeric, or when the range is 0. One call-site slot every bar,
        including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n < 1:
            return 0.0
        key = ("rsi_divergence", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "w": deque(maxlen=n + 1),
                "count": 0,
                "value": 0.0,
            }
            bucket[key] = st
        x = self._finite_or_none(self._series_last(series))
        w: deque[float | None] = st["w"]
        w.append(x)
        st["count"] = int(st["count"]) + 1
        if int(st["count"]) <= n:
            st["value"] = 0.0
            return 0.0
        vals = [v for v in w if v is not None]
        if len(vals) < 2 or x is None:
            st["value"] = 0.0
            return 0.0
        lo = min(vals)
        hi = max(vals)
        rng = hi - lo
        val = (x - lo) / rng * 2.0 - 1.0 if rng > 0 else 0.0
        st["value"] = val
        return val

    def _fractal_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        period: int,
    ) -> dict[str, bool]:
        """Incremental fractal matching full ``ta.fractal`` last sample.

        Chart high/low. Warmup is ``2*period+1`` bars (both flags False). The
        current (last) bar is a high/low fractal if it equals max/min of the
        last ``period+1`` samples — the live-bar slice
        ``[i-period : i+period+1]`` with no future bars yet. One call-site
        slot every bar, including warmup.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        off = {"is_high_fractal": False, "is_low_fractal": False}
        if n < 1:
            return off
        need = 2 * n + 1
        cmp_len = n + 1
        key = ("fractal", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h": deque(maxlen=cmp_len),
                "l": deque(maxlen=cmp_len),
                "count": 0,
                "value": off,
            }
            bucket[key] = st
        h = self._finite_or_none(self._series_last(highs))
        lo = self._finite_or_none(self._series_last(lows))
        hw: deque[float | None] = st["h"]
        lw: deque[float | None] = st["l"]
        hw.append(h)
        lw.append(lo)
        st["count"] = int(st["count"]) + 1
        if int(st["count"]) < need:
            st["value"] = off
            return off
        hvals = [v for v in hw if v is not None]
        lvals = [v for v in lw if v is not None]
        is_high = h is not None and bool(hvals) and h == max(hvals)
        is_low = lo is not None and bool(lvals) and lo == min(lvals)
        val = {"is_high_fractal": is_high, "is_low_fractal": is_low}
        st["value"] = val
        return val

    def _engulfing_inc_update(
        self,
        opens: Any,
        closes: Any,
    ) -> dict[str, bool | float]:
        """Incremental engulfing matching full ``ta.engulfing`` last sample.

        Last two opens/closes (high/low unused). Warmup is 2 bars (both flags
        False, strength 0.0). One call-site slot every bar, including warmup.
        """
        slot = self._ta_next_slot()
        off: dict[str, bool | float] = {
            "is_bullish": False,
            "is_bearish": False,
            "pattern_strength": 0.0,
        }
        key = ("engulfing", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"prev_o": None, "prev_c": None, "count": 0, "value": off}
            bucket[key] = st
        o = self._finite_or_none(self._series_last(opens))
        c = self._finite_or_none(self._series_last(closes))
        st["count"] = int(st["count"]) + 1
        prev_o = st["prev_o"]
        prev_c = st["prev_c"]
        if int(st["count"]) < 2 or prev_o is None or prev_c is None or o is None or c is None:
            st["prev_o"] = o
            st["prev_c"] = c
            st["value"] = off
            return off
        is_bullish = o < prev_c and c > prev_o and c > o
        is_bearish = o > prev_c and c < prev_o and c < o
        if is_bullish:
            engulf_amount = max(
                0,
                min(1, (c - prev_o) / abs(prev_o - prev_c + 0.0001)),
            )
        elif is_bearish:
            engulf_amount = max(
                0,
                min(1, (prev_o - c) / abs(prev_c - prev_o + 0.0001)),
            )
        else:
            engulf_amount = 0.0
        val: dict[str, bool | float] = {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "pattern_strength": engulf_amount,
        }
        st["prev_o"] = o
        st["prev_c"] = c
        st["value"] = val
        return val

    def _hammer_inc_update(
        self,
        opens: Any,
        highs: Any,
        lows: Any,
        closes: Any,
    ) -> dict[str, bool | float]:
        """Incremental hammer/doji matching full ``ta.hammer`` last sample.

        Last 1 OHLC. Defined on bar 0. One call-site slot every bar.
        """
        self._ta_next_slot()
        off: dict[str, bool | float] = {
            "is_hammer": False,
            "is_doji": False,
            "pattern_strength": 0.0,
        }
        o = self._finite_or_none(self._series_last(opens))
        h = self._finite_or_none(self._series_last(highs))
        lo = self._finite_or_none(self._series_last(lows))
        c = self._finite_or_none(self._series_last(closes))
        if o is None or h is None or lo is None or c is None:
            return off
        body_size = abs(c - o)
        total_range = h - lo
        lower_wick = min(o, c) - lo
        upper_wick = h - max(o, c)
        is_doji = body_size < total_range * 0.1
        is_hammer = body_size > 0 and lower_wick > body_size * 2 and upper_wick < body_size
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

    def _double_top_bottom_inc_update(
        self,
        highs: Any,
        lows: Any,
        period: int,
    ) -> dict[str, Any]:
        """Incremental double top/bottom matching full ``ta.double_top_bottom``.

        Last-N highs/lows. ``"none"`` / 0.0 while the window is short or fewer
        than 3 numeric highs. Peaks are local maxima in the numeric high window
        (seeded with the first numeric high). One call-site slot every bar,
        including warmup.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        off: dict[str, Any] = {
            "pattern_type": "none",
            "strength": 0.0,
            "breakout_level": 0.0,
        }
        if n < 1:
            return off
        key = ("double_top_bottom", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h": deque(maxlen=n),
                "l": deque(maxlen=n),
                "count": 0,
                "value": off,
            }
            bucket[key] = st
        hw: deque[Any] = st["h"]
        lw: deque[Any] = st["l"]
        hw.append(self._series_last(highs))
        lw.append(self._series_last(lows))
        st["count"] = int(st["count"]) + 1
        if int(st["count"]) < n:
            st["value"] = off
            return off
        recent_high = [v for v in hw if isinstance(v, (int, float))]
        recent_low = [v for v in lw if isinstance(v, (int, float))]
        if len(recent_high) < 3:
            st["value"] = off
            return off
        peaks = [recent_high[0]]
        for i in range(1, len(recent_high) - 1):
            if recent_high[i] > recent_high[i - 1] and recent_high[i] > recent_high[i + 1]:
                peaks.append(recent_high[i])
        if len(peaks) < 2:
            st["value"] = off
            return off
        peak_diff = abs(peaks[-1] - peaks[-2])
        avg_peak = (peaks[-1] + peaks[-2]) / 2.0
        strength = 1.0 - min(1.0, peak_diff / avg_peak) if avg_peak > 0 else 0.0
        breakout_level = min(recent_low) - (avg_peak * 0.1)
        val = {
            "pattern_type": "double_top",
            "strength": strength,
            "breakout_level": breakout_level,
        }
        st["value"] = val
        return val

    def _gap_detector_inc_update(
        self,
        highs: Any,
        lows: Any,
        prev_close: Any,
    ) -> dict[str, float | int]:
        """Incremental gap detector matching full ``ta.gap_detector`` last sample.

        Last high/low vs previous close. Zeros while any sample is missing
        (bar 0 / na prev_close). One call-site slot every bar, including warmup.
        """
        self._ta_next_slot()
        off: dict[str, float | int] = {
            "gap_size": 0.0,
            "gap_type": 0,
            "gap_percent": 0.0,
        }
        h = self._finite_or_none(self._series_last(highs))
        lo = self._finite_or_none(self._series_last(lows))
        pc = self._finite_or_none(self._series_last(prev_close))
        if h is None or lo is None or pc is None:
            return off
        upside_gap = max(0.0, lo - pc)
        downside_gap = max(0.0, pc - h)
        if upside_gap > downside_gap:
            gap_size = upside_gap
            gap_type = 1
            gap_percent = (upside_gap / pc * 100.0) if pc != 0 else 0.0
        elif downside_gap > 0:
            gap_size = downside_gap
            gap_type = -1
            gap_percent = (downside_gap / pc * 100.0) if pc != 0 else 0.0
        else:
            return off
        return {
            "gap_size": gap_size,
            "gap_type": gap_type,
            "gap_percent": gap_percent,
        }

    def _inside_bar_pattern_inc_update(
        self,
        highs: Any,
        lows: Any,
    ) -> bool:
        """Incremental inside-bar matching full ``ta.inside_bar_pattern``.

        Last 2 highs/lows: ``curr_high < prev_high and curr_low > prev_low``.
        ``False`` while shorter than 2 bars. Non-numeric samples coerce to
        0.0 (same as the full recompute). One call-site slot every bar,
        including warmup.
        """
        slot = self._ta_next_slot()
        key = ("inside_bar_pattern", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"prev_h": None, "prev_l": None, "count": 0, "value": False}
            bucket[key] = st
        h = self._series_last(highs)
        lo = self._series_last(lows)
        curr_h = h if isinstance(h, (int, float)) else 0.0
        curr_l = lo if isinstance(lo, (int, float)) else 0.0
        st["count"] = int(st["count"]) + 1
        prev_h = st["prev_h"]
        prev_l = st["prev_l"]
        if int(st["count"]) < 2 or prev_h is None or prev_l is None:
            st["prev_h"] = curr_h
            st["prev_l"] = curr_l
            st["value"] = False
            return False
        val = curr_h < prev_h and curr_l > prev_l
        st["prev_h"] = curr_h
        st["prev_l"] = curr_l
        st["value"] = val
        return val

    def _ema_cross_signal_inc_update(
        self,
        fast_ema: Any,
        slow_ema: Any,
        threshold: Any,
    ) -> dict[str, Any]:
        """Incremental ema-cross matching full ``ta.ema_cross_signal``.

        Last 2 samples of two series → ``{signal, strength, trend_direction}``.
        ``"neutral"`` / 0 while shorter than 2 bars. Non-numeric samples coerce
        to 0.0 (same as the full recompute). One call-site slot every bar,
        including warmup.
        """
        slot = self._ta_next_slot()
        off: dict[str, Any] = {
            "signal": "neutral",
            "strength": 0.0,
            "trend_direction": 0,
        }
        key = ("ema_cross_signal", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_fast": None,
                "prev_slow": None,
                "count": 0,
                "value": off,
            }
            bucket[key] = st
        f = self._series_last(fast_ema)
        s = self._series_last(slow_ema)
        curr_fast = f if isinstance(f, (int, float)) else 0.0
        curr_slow = s if isinstance(s, (int, float)) else 0.0
        th = threshold if isinstance(threshold, (int, float)) else 0.0
        st["count"] = int(st["count"]) + 1
        prev_fast = st["prev_fast"]
        prev_slow = st["prev_slow"]
        if int(st["count"]) < 2 or prev_fast is None or prev_slow is None:
            st["prev_fast"] = curr_fast
            st["prev_slow"] = curr_slow
            st["value"] = off
            return off
        diff = curr_fast - curr_slow
        prev_diff = prev_fast - prev_slow
        crossover = prev_diff <= 0 and diff > 0
        crossunder = prev_diff >= 0 and diff < 0
        strength = abs(diff)
        trend_direction = 1 if diff > 0 else -1
        if crossover and strength > th:
            signal = "buy"
        elif crossunder and strength > th:
            signal = "sell"
        else:
            signal = "neutral"
        val = {
            "signal": signal,
            "strength": strength,
            "trend_direction": trend_direction,
        }
        st["prev_fast"] = curr_fast
        st["prev_slow"] = curr_slow
        st["value"] = val
        return val

    def _rsi_oversold_overbought_inc_update(
        self,
        rsi_series: Any,
        oversold: int,
        overbought: int,
    ) -> dict[str, Any]:
        """Incremental RSI threshold matching full ``ta.rsi_oversold_overbought``.

        Last RSI sample vs two int levels → ``{is_oversold, is_overbought, rsi}``.
        ``False`` / ``rsi: None`` while the series is empty or the last sample
        is ``None``. Oversold is ``rsi < oversold``; overbought is
        ``rsi > overbought`` (equality is neither). One call-site slot every
        bar, including warmup / na.
        """
        self._ta_next_slot()
        off: dict[str, Any] = {
            "is_oversold": False,
            "is_overbought": False,
            "rsi": None,
        }
        rsi_current = self._series_last(rsi_series)
        if rsi_current is None:
            return off
        return {
            "is_oversold": rsi_current < oversold,
            "is_overbought": rsi_current > overbought,
            "rsi": rsi_current,
        }

    def _zigzag_inc_update(
        self,
        source: Any,
        threshold: Any,
    ) -> tuple[float, float, int]:
        """Incremental zigzag matching full ``ta.zigzag`` last sample.

        Last 2 numeric (non-``None``) samples → ``(recent_high, recent_low,
        direction)``. ``(nan, nan, 0)`` while fewer than 2 numeric samples.
        Direction is ``1`` if the last numeric is the pair high else ``-1``;
        percent change above the threshold forces ``1``. One call-site slot
        every bar, including warmup / na.
        """
        slot = self._ta_next_slot()
        off: tuple[float, float, int] = (math.nan, math.nan, 0)
        key = ("zigzag", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"w": deque(maxlen=2), "value": off}
            bucket[key] = st
        x = self._series_last(source)
        w: deque[Any] = st["w"]
        if x is not None:
            w.append(x)
        if len(w) < 2:
            st["value"] = off
            return off
        th = threshold if isinstance(threshold, (int, float)) else 5.0
        pair = [w[0], w[1]]
        recent_high = max(pair)
        recent_low = min(pair)
        percent_change = (recent_high - recent_low) / recent_low * 100 if recent_low else 0
        direction = 1 if recent_high == pair[-1] else -1
        val = (
            recent_high,
            recent_low,
            1 if percent_change > th else direction,
        )
        st["value"] = val
        return val

    def _volatility_regime_inc_update(
        self,
        atr_series: Any,
        period: int,
    ) -> str:
        """Incremental volatility regime matching full ``ta.volatility_regime``.

        Last-N ATR samples. ``"medium"`` while the window is short or there are
        no numeric samples. Classification: current < avg*0.5 → ``"low"``;
        current > avg*2.0 → ``"extreme"``; current > avg*1.3 → ``"high"``;
        else ``"medium"``. Non-numeric samples are skipped like the full
        recompute. One call-site slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n < 1:
            return "medium"
        key = ("volatility_regime", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"w": deque(maxlen=n), "value": "medium"}
            bucket[key] = st
        w: deque[Any] = st["w"]
        w.append(self._series_last(atr_series))
        if len(w) < n:
            st["value"] = "medium"
            return "medium"
        recent = [x for x in w if isinstance(x, (int, float))]
        if not recent:
            st["value"] = "medium"
            return "medium"
        current_atr = recent[-1]
        avg_atr = sum(recent) / len(recent)
        if current_atr < avg_atr * 0.5:
            val = "low"
        elif current_atr > avg_atr * 2.0:
            val = "extreme"
        elif current_atr > avg_atr * 1.3:
            val = "high"
        else:
            val = "medium"
        st["value"] = val
        return val

    def _momentum_filter_inc_update(
        self,
        momentum: Any,
        volume: Any,
        period: int,
    ) -> float:
        """Incremental momentum filter matching full ``ta.momentum_filter``.

        Last-N volume-weighted momentum. ``0.0`` while the window is short,
        ``period<=0``, there are no paired numeric samples, or volume_sum is
        0. ``vol_sum`` includes numeric volumes even when mom is non-numeric;
        the numerator uses only paired numeric (mom, vol) samples. One
        call-site slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n <= 0:
            return 0.0
        key = ("momentum_filter", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "m": deque(maxlen=n),
                "v": deque(maxlen=n),
                "value": 0.0,
            }
            bucket[key] = st
        wm: deque[Any] = st["m"]
        wv: deque[Any] = st["v"]
        wm.append(self._series_last(momentum))
        wv.append(self._series_last(volume))
        if len(wm) < n or len(wv) < n:
            st["value"] = 0.0
            return 0.0
        vol_sum = sum(v for v in wv if isinstance(v, (int, float)))
        mom_data = [
            (m, v) for m, v in zip(wm, wv, strict=True) if isinstance(m, (int, float)) and isinstance(v, (int, float))
        ]
        if not mom_data or vol_sum == 0:
            st["value"] = 0.0
            return 0.0
        val = sum(m * v for m, v in mom_data) / vol_sum
        st["value"] = val
        return val

    def _acceleration_factor_inc_update(
        self,
        momentum: Any,
        period: int,
    ) -> float:
        """Incremental acceleration factor matching full ``ta.acceleration_factor``.

        Last-(period+1) samples. ``0.0`` while the window is short,
        ``period<=0``, fewer than 2 numeric samples, or ``abs(old_mom) < 1e-10``.
        Else clamp ``(new_mom - old_mom) / old_mom`` to ``[-2.0, 2.0]``.
        ``new_mom`` is the last numeric in the cleaned window. One call-site
        slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n <= 0:
            return 0.0
        key = ("acceleration_factor", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"w": deque(maxlen=n + 1), "value": 0.0}
            bucket[key] = st
        w: deque[Any] = st["w"]
        w.append(self._series_last(momentum))
        if len(w) < n + 1:
            st["value"] = 0.0
            return 0.0
        momentum_clean = [m for m in w if isinstance(m, (int, float))]
        if len(momentum_clean) < 2:
            st["value"] = 0.0
            return 0.0
        old_mom = sum(momentum_clean[:-1]) / len(momentum_clean[:-1])
        new_mom = momentum_clean[-1]
        if abs(old_mom) < 1e-10:
            st["value"] = 0.0
            return 0.0
        acceleration = (new_mom - old_mom) / old_mom
        val = max(-2.0, min(2.0, acceleration))
        st["value"] = val
        return val

    def _mean_reversion_score_inc_update(
        self,
        close: Any,
        sma: Any,
        stdev: Any,
        period: int,
    ) -> float:
        """Incremental mean reversion score matching full ``ta.mean_reversion_score``.

        Period is a warmup gate (need ``period`` samples of close and sma),
        not a rolling window. After warmup, last samples only: non-numeric
        last close/sma → 100.0, last stdev → 1.0; ``sd==0`` or short window
        or ``period<=0`` → 50.0; else clamp ``min(100, abs(c-s)/sd * 20)``
        to ``[0, 100]``. One call-site slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n <= 0:
            return 50.0
        key = ("mean_reversion_score", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"count_c": 0, "count_s": 0, "value": 50.0}
            bucket[key] = st
        c_last = self._series_last(close)
        s_last = self._series_last(sma)
        sd_last = self._series_last(stdev)
        st["count_c"] = int(st["count_c"]) + 1
        st["count_s"] = int(st["count_s"]) + 1
        if st["count_c"] < n or st["count_s"] < n:
            st["value"] = 50.0
            return 50.0
        c = c_last if isinstance(c_last, (int, float)) else 100.0
        s = s_last if isinstance(s_last, (int, float)) else 100.0
        sd = sd_last if isinstance(sd_last, (int, float)) else 1.0
        if sd == 0:
            st["value"] = 50.0
            return 50.0
        distance = abs(c - s) / sd
        score = min(100.0, distance * 20)
        val = max(0.0, min(100.0, score))
        st["value"] = val
        return val

    def _market_condition_inc_update(
        self,
        close: Any,
        atr: Any,
        sma_period: int,
        stdev_period: int,
    ) -> str:
        """Incremental market condition matching full ``ta.market_condition``.

        Last-N close deque (``maxlen=max(sma_period, stdev_period)``) plus last
        ATR sample. ``"ranging"`` while the window is short or either period
        is ``<=0``. After warmup, last close/atr vs ``_sma`` / ``_stdev`` on
        the chronological close window: stdev > atr*1.5 → ``"volatile"``;
        close > sma and atr > 0.5 → ``"trending_up"``; close < sma and
        atr > 0.5 → ``"trending_down"``; else ``"ranging"``. Non-numeric last
        close → 0, last atr → 1.0. One call-site slot every bar, including
        warmup / na.
        """
        sma_n = int(sma_period) if sma_period is not None else 0
        stdev_n = int(stdev_period) if stdev_period is not None else 0
        slot = self._ta_next_slot()
        if sma_n <= 0 or stdev_n <= 0:
            return "ranging"
        win = max(sma_n, stdev_n)
        key = ("market_condition", slot, sma_n, stdev_n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"w": deque(maxlen=win), "atr": None, "value": "ranging"}
            bucket[key] = st
        w: deque[Any] = st["w"]
        w.append(self._series_last(close))
        st["atr"] = self._series_last(atr)
        if len(w) < win:
            st["value"] = "ranging"
            return "ranging"
        close_window = list(w)
        c_last = close_window[-1]
        a_last = st["atr"]
        current_close = c_last if isinstance(c_last, (int, float)) else 0
        current_atr = a_last if isinstance(a_last, (int, float)) else 1.0
        sma_list = self._sma(close_window, sma_n)
        current_sma = sma_list[-1] if sma_list and sma_list[-1] is not None else current_close
        stdev_val = self._stdev(close_window, stdev_n)
        if stdev_val and stdev_val > (current_atr * 1.5):
            val = "volatile"
        elif current_close > current_sma and current_atr > 0.5:
            val = "trending_up"
        elif current_close < current_sma and current_atr > 0.5:
            val = "trending_down"
        else:
            val = "ranging"
        st["value"] = val
        return val

    def _order_flow_imbalance_inc_update(
        self,
        high: Any,
        low: Any,
        close: Any,
        volume: Any,
        period: int,
    ) -> float:
        """Incremental order flow imbalance matching full ``ta.order_flow_imbalance``.

        Last-N high/low/close/volume deques. ``0.0`` while the window is short,
        ``period<=0``, or buy+sell volume total is 0. Bars with ``high<=low``
        (zero range / non-numeric coerced to 0) skip. Else close above the
        high/low midpoint counts as buy volume, otherwise sell. One call-site
        slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n <= 0:
            return 0.0
        key = ("order_flow_imbalance", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h": deque(maxlen=n),
                "l": deque(maxlen=n),
                "c": deque(maxlen=n),
                "v": deque(maxlen=n),
                "value": 0.0,
            }
            bucket[key] = st
        wh: deque[Any] = st["h"]
        wl: deque[Any] = st["l"]
        wc: deque[Any] = st["c"]
        wv: deque[Any] = st["v"]
        wh.append(self._series_last(high))
        wl.append(self._series_last(low))
        wc.append(self._series_last(close))
        wv.append(self._series_last(volume))
        if len(wh) < n or len(wl) < n:
            st["value"] = 0.0
            return 0.0
        buy_vol = 0.0
        sell_vol = 0.0
        for h_raw, l_raw, c_raw, v_raw in zip(wh, wl, wc, wv, strict=True):
            h_val = h_raw if isinstance(h_raw, (int, float)) else 0
            low_val = l_raw if isinstance(l_raw, (int, float)) else 0
            c_val = c_raw if isinstance(c_raw, (int, float)) else 0
            v_val = v_raw if isinstance(v_raw, (int, float)) else 0
            if h_val > low_val:
                midpoint = (h_val + low_val) / 2
                if c_val > midpoint:
                    buy_vol += v_val
                else:
                    sell_vol += v_val
        total = buy_vol + sell_vol
        if total == 0:
            st["value"] = 0.0
            return 0.0
        val = (buy_vol - sell_vol) / total
        st["value"] = val
        return val

    def _volume_thrust_inc_update(
        self,
        close: Any,
        volume: Any,
        vol_sma: Any,
        sensitivity: Any,
    ) -> bool:
        """Incremental volume thrust matching full ``ta.volume_thrust``.

        Last-2 closes + last volume + last vol_sma. ``False`` while any series
        is empty (no samples yet). Non-numeric last close → 100.0, last volume
        / vol_sma → 1000.0; missing / non-numeric prev close → 100.0. After
        samples: volume spike ``v > vs*(1+sensitivity)`` and price move
        ``abs(c-c_prev)/c_prev > 0.01`` (False if ``c_prev==0``). One call-site
        slot every bar, including warmup / empty.
        """
        slot = self._ta_next_slot()
        key = ("volume_thrust", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "c": deque(maxlen=2),
                "v": None,
                "vs": None,
                "n_c": 0,
                "n_v": 0,
                "n_vs": 0,
                "value": False,
            }
            bucket[key] = st
        wc: deque[Any] = st["c"]
        c_last = self._series_last(close)
        v_last = self._series_last(volume)
        vs_last = self._series_last(vol_sma)
        n_c = int(st["n_c"])
        if not (type(close) is list and not close) and not (close is None and n_c == 0):
            wc.append(c_last)
            st["n_c"] = n_c + 1
        n_v = int(st["n_v"])
        if not (type(volume) is list and not volume) and not (volume is None and n_v == 0):
            st["v"] = v_last
            st["n_v"] = n_v + 1
        n_vs = int(st["n_vs"])
        if not (type(vol_sma) is list and not vol_sma) and not (vol_sma is None and n_vs == 0):
            st["vs"] = vs_last
            st["n_vs"] = n_vs + 1
        if int(st["n_c"]) < 1 or int(st["n_v"]) < 1 or int(st["n_vs"]) < 1:
            st["value"] = False
            return False
        c_raw = wc[-1]
        c_val = c_raw if isinstance(c_raw, (int, float)) else 100.0
        if len(wc) > 1:
            p_raw = wc[-2]
            c_prev = p_raw if isinstance(p_raw, (int, float)) else 100.0
        else:
            c_prev = 100.0
        v_val = st["v"] if isinstance(st["v"], (int, float)) else 1000.0
        vs_val = st["vs"] if isinstance(st["vs"], (int, float)) else 1000.0
        sens = sensitivity if isinstance(sensitivity, (int, float)) else 0.3
        volume_spike = v_val > vs_val * (1 + sens)
        price_move = abs(c_val - c_prev) / c_prev > 0.01 if c_prev != 0 else False
        val = bool(volume_spike and price_move)
        st["value"] = val
        return val

    def _liquidity_score_inc_update(
        self,
        volume: Any,
        volatility: Any,
        spread: Any,
        period: int,
    ) -> float:
        """Incremental liquidity score matching full ``ta.liquidity_score``.

        Last-N volume/volatility/spread deques. ``50.0`` while the window is
        short or ``period<=0``. Last-N numeric averages divide by period even
        when some samples are non-numeric: ``vol_score = min(100, vol_avg/100)``,
        ``volatility_score = max(0, 100 - vol_avg_volatility*50)``,
        ``spread_score = max(0, 100 - spread_avg*100)``; 0.4/0.3/0.3 mix, clamp
        0-100. One call-site slot every bar, including warmup / na.
        """
        n = int(period) if period is not None else 0
        slot = self._ta_next_slot()
        if n <= 0:
            return 50.0
        key = ("liquidity_score", slot, n)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "vol": deque(maxlen=n),
                "vola": deque(maxlen=n),
                "sp": deque(maxlen=n),
                "value": 50.0,
            }
            bucket[key] = st
        wvol: deque[Any] = st["vol"]
        wvola: deque[Any] = st["vola"]
        wsp: deque[Any] = st["sp"]
        wvol.append(self._series_last(volume))
        wvola.append(self._series_last(volatility))
        wsp.append(self._series_last(spread))
        if len(wvol) < n or len(wvola) < n or len(wsp) < n:
            st["value"] = 50.0
            return 50.0
        vol_avg = sum(v for v in wvol if isinstance(v, (int, float))) / n
        vol_score = min(100.0, vol_avg / 100.0)
        vol_avg_volatility = sum(v for v in wvola if isinstance(v, (int, float))) / n
        volatility_score = max(0.0, 100.0 - vol_avg_volatility * 50.0)
        spread_avg = sum(s for s in wsp if isinstance(s, (int, float))) / n
        spread_score = max(0.0, 100.0 - spread_avg * 100.0)
        liquidity = vol_score * 0.4 + volatility_score * 0.3 + spread_score * 0.3
        val = max(0.0, min(100.0, liquidity))
        st["value"] = val
        return val

    def _fear_greed_index_inc_update(
        self,
        rsi: Any,
        vix: Any,
        put_call: Any,
        breadth: Any,
    ) -> float:
        """Incremental fear greed index matching full ``ta.fear_greed_index``.

        Last samples of rsi / vix / put_call / breadth. Empty or missing last
        sample uses the same defaults as non-numeric: 50 / 2 / 1 / 0.5. Mix
        ``(rsi_fear + vix_fear + pc_fear + b_fear) / 4``, clamp [-100, 100].
        One call-site slot every bar, including empty.
        """
        slot = self._ta_next_slot()
        key = ("fear_greed_index", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 0.0}
            bucket[key] = st
        rsi_last = self._series_last(rsi)
        vix_last = self._series_last(vix)
        pc_last = self._series_last(put_call)
        b_last = self._series_last(breadth)
        rsi_val = rsi_last if isinstance(rsi_last, (int, float)) else 50.0
        vix_val = vix_last if isinstance(vix_last, (int, float)) else 2.0
        pc_val = pc_last if isinstance(pc_last, (int, float)) else 1.0
        b_val = b_last if isinstance(b_last, (int, float)) else 0.5
        rsi_fear = (rsi_val - 50) * 1.0
        vix_fear = (vix_val - 2.0) * 10.0
        pc_fear = (1.0 - pc_val) * 50.0
        b_fear = (b_val - 0.5) * 100.0
        fear_index = (rsi_fear + vix_fear + pc_fear + b_fear) / 4
        val = max(-100.0, min(100.0, fear_index))
        st["value"] = val
        return val

    def _crowd_sentiment_inc_update(
        self,
        price_agr: Any,
        vol_agr: Any,
        time_agr: Any,
    ) -> float:
        """Incremental crowd sentiment matching full ``ta.crowd_sentiment``.

        Last samples of price / volume / time agreement. Empty or missing last
        sample uses the same default as non-numeric: 0.5. Mix
        ``((p + v + t) / 3) * 100``, clamp [0, 100]. One call-site slot every
        bar, including empty.
        """
        slot = self._ta_next_slot()
        key = ("crowd_sentiment", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 50.0}
            bucket[key] = st
        p_last = self._series_last(price_agr)
        v_last = self._series_last(vol_agr)
        t_last = self._series_last(time_agr)
        p = p_last if isinstance(p_last, (int, float)) else 0.5
        v = v_last if isinstance(v_last, (int, float)) else 0.5
        t = t_last if isinstance(t_last, (int, float)) else 0.5
        consensus = ((p + v + t) / 3) * 100
        val = max(0.0, min(100.0, consensus))
        st["value"] = val
        return val

    def _smart_money_flow_inc_update(
        self,
        price_change: Any,
        volume: Any,
        time_high: Any,
        time_low: Any,
    ) -> float:
        """Incremental smart money flow matching full ``ta.smart_money_flow``.

        Last samples of price_change / volume / time_since_high / time_since_low.
        Empty or missing last sample uses the same defaults as non-numeric:
        0 / 1000 / 10 / 10. Volume-scaled signed flow from last price_change vs
        time_since_high/low, clamp [-1, 1]. One call-site slot every bar,
        including empty.
        """
        slot = self._ta_next_slot()
        key = ("smart_money_flow", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 0.0}
            bucket[key] = st
        p_last = self._series_last(price_change)
        v_last = self._series_last(volume)
        th_last = self._series_last(time_high)
        tl_last = self._series_last(time_low)
        p = p_last if isinstance(p_last, (int, float)) else 0.0
        v = v_last if isinstance(v_last, (int, float)) else 1000.0
        th = th_last if isinstance(th_last, (int, float)) else 10
        tl = tl_last if isinstance(tl_last, (int, float)) else 10
        vol_factor = min(1.0, v / 5000.0)
        if p > 0 and th < tl:
            flow = vol_factor * 0.8
        elif p < 0 and tl < th:
            flow = -vol_factor * 0.8
        else:
            flow = 0.0
        val = max(-1.0, min(1.0, flow))
        st["value"] = val
        return val

    def _trend_confirmation_score_inc_update(
        self,
        momentum: Any,
        trend_alignment: Any,
        strength: Any,
        rsi: Any,
        rsi_alignment: Any,
    ) -> float:
        """Incremental trend confirmation matching full ``ta.trend_confirmation_score``.

        Last samples of momentum / trend_alignment / strength / rsi /
        rsi_alignment. Empty or missing last sample uses the same defaults as
        non-numeric: 0 / 0 / 1 / 50 / 0. Five last samples mixed, clamp
        [0, 100]. One call-site slot every bar, including empty.
        """
        slot = self._ta_next_slot()
        key = ("trend_confirmation_score", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 33.5}
            bucket[key] = st
        m_last = self._series_last(momentum)
        t_last = self._series_last(trend_alignment)
        s_last = self._series_last(strength)
        r_last = self._series_last(rsi)
        a_last = self._series_last(rsi_alignment)
        m = m_last if isinstance(m_last, (int, float)) else 0.0
        t = t_last if isinstance(t_last, (int, float)) else 0.0
        s = s_last if isinstance(s_last, (int, float)) else 1.0
        r = r_last if isinstance(r_last, (int, float)) else 50.0
        a = a_last if isinstance(a_last, (int, float)) else 0.0
        momentum_score = min(100.0, abs(m) * 20.0)
        trend_score = max(0.0, (t + 1.0) / 2.0 * 100.0)
        strength_score = min(100.0, s * 50.0)
        rsi_score = min(100.0, abs(r - 50.0) * 2.0) if abs(r - 50.0) > 10.0 else 40.0
        alignment_bonus = 20.0 if abs(a) > 0.5 else 0.0
        total = momentum_score * 0.25 + trend_score * 0.3 + strength_score * 0.25 + rsi_score * 0.15 + alignment_bonus
        val = max(0.0, min(100.0, total))
        st["value"] = val
        return val

    def _atr_stop_inc_update(
        self,
        atr_value: Any,
        multiplier: Any,
    ) -> dict[str, float | None]:
        """Incremental ATR stop matching full ``ta.atr_stop``.

        Last ATR sample and last chart close. Default multiplier 2.0.
        Non-numeric / ``<= 0`` ATR or no close →
        ``{long_stop: None, short_stop: None}``. One call-site slot every
        bar, including empty.
        """
        self._ta_next_slot()
        off: dict[str, float | None] = {"long_stop": None, "short_stop": None}
        a_last = self._series_last(atr_value)
        if not isinstance(a_last, (int, float)) or a_last <= 0:
            return off
        c_last = self._series_last(self._context_source("close"))
        if not isinstance(c_last, (int, float)):
            return off
        m_last = self._series_last(multiplier)
        m = float(m_last) if isinstance(m_last, (int, float)) else 2.0
        return {
            "long_stop": c_last - (a_last * m),
            "short_stop": c_last + (a_last * m),
        }

    def _max_loss_level_inc_update(
        self,
        entry: Any,
        account: Any,
        max_loss_pct: Any,
    ) -> float:
        """Incremental max-loss stop matching full ``ta.max_loss_level``.

        Last samples of entry / account / max_loss_pct. Empty or missing last
        sample uses the same defaults as non-numeric: 100 / 10000 / 1.0.
        ``entry <= 0`` or ``shares <= 0`` → 0.0. Clamp stop ``>= 0``. One
        call-site slot every bar, including empty.
        """
        slot = self._ta_next_slot()
        key = ("max_loss_level", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 99.0}
            bucket[key] = st
        e_last = self._series_last(entry)
        a_last = self._series_last(account)
        p_last = self._series_last(max_loss_pct)
        e = e_last if isinstance(e_last, (int, float)) else 100.0
        a = a_last if isinstance(a_last, (int, float)) else 10000.0
        p = p_last if isinstance(p_last, (int, float)) else 1.0
        max_loss_amount = a * (p / 100.0)
        if e > 0:
            shares = a / e
            stop_price = e - (max_loss_amount / shares) if shares > 0 else 0.0
            val = max(0.0, stop_price)
        else:
            val = 0.0
        st["value"] = val
        return val

    def _profit_lock_level_inc_update(
        self,
        entry: Any,
        current: Any,
        trail_pct: Any,
        direction: Any,
    ) -> float:
        """Incremental profit-lock stop matching full ``ta.profit_lock_level``.

        Last samples of entry / current / trail_pct / direction. Empty or
        missing last sample uses the same defaults as non-numeric:
        100 / 100 / 0.05 / 1.0. ``trail_pct`` is clamped to ``[0, 1]``.
        Long (``direction > 0``): ``max(entry*0.9, current*(1-trail_pct))``.
        Short: ``min(entry*1.1, current*(1+trail_pct))``. One call-site
        slot every bar, including empty.
        """
        slot = self._ta_next_slot()
        key = ("profit_lock_level", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"value": 95.0}
            bucket[key] = st
        e_last = self._series_last(entry)
        c_last = self._series_last(current)
        t_last = self._series_last(trail_pct)
        d_last = self._series_last(direction)
        e = e_last if isinstance(e_last, (int, float)) else 100.0
        c = c_last if isinstance(c_last, (int, float)) else 100.0
        t = t_last if isinstance(t_last, (int, float)) else 0.05
        d = d_last if isinstance(d_last, (int, float)) else 1.0
        t = max(0.0, min(1.0, t))
        if d > 0:
            val = max(e * 0.9, c - c * t)
        else:
            val = min(e * 1.1, c + c * t)
        st["value"] = val
        return val

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
                "na_count": 0,
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
            if old_s is None or old_v is None:
                st["na_count"] -= 1
            else:
                try:
                    st["sum_pv"] -= float(old_s) * float(old_v)
                    st["sum_v"] -= float(old_v)
                except (TypeError, ValueError):
                    st["na_count"] -= 1
        s_win.append(x)
        v_win.append(v)
        if x is None or v is None:
            st["na_count"] += 1
        else:
            try:
                st["sum_pv"] += float(x) * float(v)
                st["sum_v"] += float(v)
            except (TypeError, ValueError):
                st["na_count"] += 1
        if len(s_win) < period:
            st["value"] = None
            return None
        # Any na in window → na (match NaN windows); running sums stay exact.
        if st["na_count"] > 0:
            st["value"] = None
            return None
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
    ) -> float | None:
        """Incremental CCI matching compile ``numba_cci_inc`` (last value).

        Window of typical price; SMA via running sum; mean absolute deviation
        recomputed over the window each bar (O(period)). Warm-up and na windows
        return ``None`` (never silent 0). Mean deviation of zero after a full
        window still returns ``0.0`` (compile).
        """
        if period <= 0:
            return None
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
                "value": None,
            }
            bucket[key] = st
        h = self._finite_or_none(self._series_last(highs))
        l = self._finite_or_none(self._series_last(lows))
        c = self._finite_or_none(self._series_last(closes))
        tp: float | None
        if h is None or l is None or c is None:
            tp = None
        else:
            tp = (h + l + c) / 3.0
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
        if len(window) < period or st["count"] != period:
            st["value"] = None
            return None
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
        if mean_dev not in {None, 0}:
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
        # Reference Pine ta.tsi returns the raw ratio in [-1, 1], not percent.
        st["value"] = float(e2) / float(a2)
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
    ) -> float | None:
        """Incremental Williams %R matching full ``_wpr`` (last value).

        Full path returns ``na`` when under-warmed; high==low stays ``0.0``.
        """
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("wpr", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "h": {"dq": deque(), "bad": deque(), "count": 0, "na_count": 0},
                "l": {"dq": deque(), "bad": deque(), "count": 0, "na_count": 0},
                "value": 0.0,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        c = self._series_last(closes)
        # Monotonic-deque extremes (amortized O(1)); na anywhere → 0.0
        # (full path: float(None) raises → caught → 0.0).
        hh = self._extreme_window_push(st["h"], h, period, mode="high")
        ll = self._extreme_window_push(st["l"], l, period, mode="low")
        if hh is None or ll is None:
            st["value"] = None
            return None
        if hh == ll:
            st["value"] = 0.0
            return 0.0
        if c is None:
            st["value"] = None
            return None
        st["value"] = -100.0 * (hh - float(c)) / (hh - ll)
        return float(st["value"])

    def _uo_avg(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        i: int,
        length: int,
    ) -> float | None:
        """Buying-pressure / Williams true-range average ending at ``i``."""
        if length <= 0 or i < length:
            return None
        bp = 0.0
        tr = 0.0
        for j in range(i - length + 1, i + 1):
            prev = closes[j - 1]
            h = highs[j]
            lo = lows[j]
            c = closes[j]
            if prev is None or h is None or lo is None or c is None:
                return None
            try:
                prevf = float(prev)
                hf = float(h)
                lf = float(lo)
                cf = float(c)
            except (TypeError, ValueError):
                return None
            # NaN
            if prevf != prevf or hf != hf or lf != lf or cf != cf:
                return None
            low_ref = lf if lf < prevf else prevf
            high_ref = hf if hf > prevf else prevf
            bp += cf - low_ref
            tr += high_ref - low_ref
        if tr == 0.0:
            return None
        return bp / tr

    def _uo_last(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        n1: int,
        n2: int,
        n3: int,
    ) -> float | None:
        """Ultimate Oscillator at the last bar. Weights are 4, 2, 1 by argument."""
        if n1 <= 0 or n2 <= 0 or n3 <= 0:
            return None
        n = min(len(highs), len(lows), len(closes))
        if n <= max(n1, n2, n3):
            return None
        i = n - 1
        a1 = self._uo_avg(highs, lows, closes, i, n1)
        a2 = self._uo_avg(highs, lows, closes, i, n2)
        a3 = self._uo_avg(highs, lows, closes, i, n3)
        if a1 is None or a2 is None or a3 is None:
            return None
        return 100.0 * (4.0 * a1 + 2.0 * a2 + a3) / 7.0

    def _uo_inc_update(self, n1: int, n2: int, n3: int) -> float | None:
        """Bar-mode Ultimate Oscillator. O(longest window), not the full history."""
        if n1 <= 0 or n2 <= 0 or n3 <= 0:
            return None
        need = max(n1, n2, n3)
        slot = self._ta_next_slot()
        key = ("uo", slot, n1, n2, n3)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"prev": None, "window": deque(), "value": None}
            bucket[key] = st
        h = self._series_last(self._context_source("high"))
        lo = self._series_last(self._context_source("low"))
        c = self._series_last(self._context_source("close"))
        prev = st["prev"]
        st["prev"] = c
        bp: float | None = None
        tr: float | None = None
        if prev is not None and h is not None and lo is not None and c is not None:
            try:
                prevf = float(prev)
                hf = float(h)
                lf = float(lo)
                cf = float(c)
                if prevf == prevf and hf == hf and lf == lf and cf == cf:
                    low_ref = lf if lf < prevf else prevf
                    high_ref = hf if hf > prevf else prevf
                    bp = cf - low_ref
                    tr = high_ref - low_ref
            except (TypeError, ValueError):
                bp = None
                tr = None
        window: deque[tuple[float | None, float | None]] = st["window"]
        window.append((bp, tr))
        if len(window) > need:
            window.popleft()
        if len(window) < need:
            st["value"] = None
            return None
        items = list(window)

        def avg(length: int) -> float | None:
            bp_s = 0.0
            tr_s = 0.0
            for b, t in items[-length:]:
                if b is None or t is None:
                    return None
                bp_s += b
                tr_s += t
            if tr_s == 0.0:
                return None
            return bp_s / tr_s

        a1 = avg(n1)
        a2 = avg(n2)
        a3 = avg(n3)
        if a1 is None or a2 is None or a3 is None:
            st["value"] = None
            return None
        st["value"] = 100.0 * (4.0 * a1 + 2.0 * a2 + a3) / 7.0
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
        """Incremental population variance matching full ``_variance`` (ddof=0).

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
        var = (ss - (s * s) / n) / n
        var = max(var, 0.0)
        st["value"] = var
        return st.get("value")

    @staticmethod
    def _wma_from_window(window: deque[Any] | list[Any], period: int) -> float | None:
        """WMA over a fixed-length window matching full ``_wma`` (strict na)."""
        recomputed = TechnicalHelpers._wma_recompute_window(window, period)
        if recomputed is None:
            return None
        _s, ws = recomputed
        return ws / (period * (period + 1) / 2.0)

    def _hma_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental Hull MA: WMA(2*WMA(n/2)-WMA(n), sqrt(n)) last value.

        Three nested O(1) WMA states. Matches full ``_hma`` readiness: first
        non-None after ``period + sqrt(n) - 1`` samples. Strict window
        (inner na poisons the outer WMA for ``sqrt(n)`` bars).
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
                "half": self._wma_state_new(),
                "full": self._wma_state_new(),
                "outer": self._wma_state_new(),
                "value": None,
            }
            bucket[key] = st
        x = self._series_last(series)
        wh = self._wma_state_step(st["half"], x, half)
        wf = self._wma_state_step(st["full"], x, period)
        if wh is None or wf is None:
            self._wma_state_step(st["outer"], None, sqrt_n)
            st["value"] = None
            return None
        st["value"] = self._wma_state_step(st["outer"], 2.0 * float(wh) - float(wf), sqrt_n)
        return st.get("value")

    def _rising_inc_update(self, series: list[Any], period: int) -> bool:
        """Incremental ``ta.rising`` matching full ``_rising`` last-value semantics."""
        if period < 1:
            return False
        need = period + 1
        slot = self._ta_next_slot()
        key = ("rising", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=need), "value": False}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < need:
            st["value"] = False
            return False
        # Delegate to full helper so MRO / oracle semantics stay identical.
        st["value"] = bool(self._rising(list(window), period))
        return bool(st["value"])

    def _falling_inc_update(self, series: list[Any], period: int) -> bool:
        """Incremental ``ta.falling`` matching full ``_falling`` last-value semantics."""
        if period < 1:
            return False
        need = period + 1
        slot = self._ta_next_slot()
        key = ("falling", slot, period)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=need), "value": False}
            bucket[key] = st
        x = self._series_last(series)
        window: deque[Any] = st["window"]
        window.append(x)
        if len(window) < need:
            st["value"] = False
            return False
        st["value"] = bool(self._falling(list(window), period))
        return bool(st["value"])

    def _rci_spearman(self, window: list[Any]) -> float | None:
        """Spearman rho of time vs value ranks. Any na → na (match ``numba_rci``).

        Rank of index ``a`` is ``#{b: vb < va} + #{b: vb == va and b < a}``,
        i.e. the position in a stable sort by value — so one O(n log n) sort
        replaces the former O(n²) pairwise scan (this runs per bar).
        """
        n = len(window)
        if n < 2:
            return None
        vals: list[float] = []
        for v in window:
            f = self._finite_or_none(v)
            if f is None:
                return None
            vals.append(f)
        d2 = 0.0
        for pos, idx in enumerate(sorted(range(n), key=vals.__getitem__)):
            d = float(idx - pos)
            d2 += d * d
        denom = float(n) * (float(n) * float(n) - 1.0)
        if denom == 0.0:
            return None
        return 1.0 - (6.0 * d2) / denom

    def _rci_inc_update(self, series: Any, length: int) -> float | None:
        """Incremental ``ta.rci`` from last-sample sources (``input.source``)."""
        length = int(length)
        if length < 2:
            return None
        slot = self._ta_next_slot()
        key = ("rci", slot, length)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=length), "value": None}
            bucket[key] = st
        window: deque[Any] = st["window"]
        window.append(self._series_last(series))
        if len(window) < length:
            st["value"] = None
            return None
        st["value"] = self._rci_spearman(list(window))
        return st.get("value")

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

    def _mode_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental mode matching full ``_mode`` (last value)."""
        if period <= 0:
            return None
        slot = self._ta_next_slot()
        key = ("mode", slot, period)
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
        valid = [v for v in window if v is not None]
        if not valid:
            st["value"] = None
            return None
        try:
            st["value"] = float(statistics.mode(valid))
        except statistics.StatisticsError:
            st["value"] = float(valid[0])
        return st.get("value")

    def _cog_inc_update(self, series: list[Any], length: int) -> float:
        """Incremental Center of Gravity matching full ``_builtin_ta_cog``."""
        if length < 1:
            return math.nan
        slot = self._ta_next_slot()
        key = ("cog", slot, int(length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=length)}
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None
        if raw is None:
            x = None
        else:
            try:
                x = float(raw)
                if x != x:
                    x = None
            except (TypeError, ValueError):
                x = None
        window: deque[float | None] = st["window"]
        window.append(x)
        if len(window) < length:
            return math.nan
        num_sum = sum((i + 1) * val for i, val in enumerate(reversed(window)) if val is not None)
        den_sum = sum(val for val in window if val is not None)
        if den_sum == 0:
            return math.nan
        return -num_sum / den_sum

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
        if len(window) < period:
            window.append(x)
            st["value"] = None
            return None
        if x is None or any(v is None for v in window):
            window.append(x)
            st["value"] = None
            return None
        count_below = sum(1 for v in window if float(v) <= x)
        st["value"] = (count_below / period) * 100.0
        window.append(x)
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

    def _highestbars_inc_update(self, series: list[Any], period: int) -> int | None:
        """Incremental highestbars matching full ``_highestbars`` (last offset)."""
        if period <= 0:
            return None
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
            st["value"] = None
            return None
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            # >= prefers the newest extreme on ties (reference Pine).
            if best_v is None or fv >= best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            st["value"] = None
            return None
        # Offset from current bar: 0 = current, -1 = previous, ...
        st["value"] = best_i - (period - 1)
        return int(st["value"])

    def _lowestbars_inc_update(self, series: list[Any], period: int) -> int | None:
        """Incremental lowestbars matching full ``_lowestbars`` (last offset)."""
        if period <= 0:
            return None
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
            st["value"] = None
            return None
        best_i: int | None = None
        best_v: float | None = None
        for i, v in enumerate(window):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            # <= prefers the newest extreme on ties (reference Pine).
            if best_v is None or fv <= best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            st["value"] = None
            return None
        st["value"] = best_i - (period - 1)
        return int(st["value"])

    def _vwap_inc_update(
        self,
        source: list[Any],
        volume: list[Any] | None = None,
        *,
        anchor: Any = None,
        stdev_mult: Any = None,
    ) -> float | tuple[float, float, float] | None:
        """Incremental cumulative VWAP matching bar-mode full recompute last value.

        Sums price*volume / sum(volume) over all bars seen at this call site.
        None prices are skipped (same as full ``_builtin_ta_vwap`` loop).
        When *anchor* is truthy, the cumulative window restarts on this bar.
        When *stdev_mult* is set, returns ``(vwap, upper, lower)`` using
        volume-weighted variance ``E[x^2] - E[x]^2``.
        """
        slot = self._ta_next_slot()
        key = ("vwap", slot)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"cum_pv": 0.0, "cum_v": 0.0, "cum_p2v": 0.0, "value": None, "n": 0}
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
                    st["cum_p2v"] = 0.0
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
        st["cum_p2v"] = float(st.get("cum_p2v", 0.0)) + price * price * v
        st["n"] = int(st["n"]) + 1
        if st["cum_v"]:
            vwap = st["cum_pv"] / st["cum_v"]
        else:
            vwap = price
        if stdev_mult is None:
            st["value"] = vwap
            return vwap
        m_raw = self._series_last(stdev_mult) if not isinstance(stdev_mult, (bool, int, float)) else stdev_mult
        try:
            m = float(m_raw) if m_raw is not None else 0.0
        except (TypeError, ValueError):
            m = 0.0
        if st["cum_v"]:
            var = st["cum_p2v"] / st["cum_v"] - vwap * vwap
            var = max(var, 0.0)
            sd = math.sqrt(var)
        else:
            sd = 0.0
        bands = (vwap, vwap + sd * m, vwap - sd * m)
        st["value"] = bands
        return bands

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

    @staticmethod
    def _linreg_from_valid(window: deque[Any] | list[Any], offset: int) -> float:
        """Skip-na OLS endpoint matching full interpret ``ta.linreg``."""
        valid_values: list[float] = []
        for v in window:
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv != fv:
                continue
            valid_values.append(fv)
        if len(valid_values) < 2:
            return math.nan
        n = len(valid_values)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(valid_values) / n
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, valid_values, strict=True))
        denominator = sum((xi - mean_x) ** 2 for xi in xs)
        if denominator == 0:
            return mean_y
        slope = numerator / denominator
        return mean_y + slope * ((n - 1 - int(offset)) - mean_x)

    @staticmethod
    def _linreg_endpoint(sum_y: float, sum_xy: float, length: int, offset: int) -> float:
        """Fitted value at ``x = length - 1 - offset`` from running sums."""
        n = float(length)
        mean_x = (n - 1.0) / 2.0
        mean_y = sum_y / n
        # sum((x - mean_x)^2) for x=0..n-1 = n(n²-1)/12
        denom = n * (n * n - 1.0) / 12.0
        if denom == 0.0:
            return mean_y
        slope = (sum_xy - mean_x * sum_y) / denom
        return mean_y + slope * ((n - 1.0 - float(offset)) - mean_x)

    def _linreg_inc_update(self, series: list[Any], length: int, offset: int = 0) -> float:
        """Incremental linear-regression endpoint matching full ``ta.linreg``.

        All-finite window: O(1) ``sum_y`` / ``sum_xy`` (x = 0..n-1 oldest→newest).
        na in window: skip-na OLS (existing interpret oracle). Result is the
        fitted value at ``x = n - 1 - offset``.
        """
        if length < 2:
            return math.nan
        slot = self._ta_next_slot()
        off = int(offset)
        key = ("linreg", slot, length, off)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "window": deque(),
                "sum_y": 0.0,
                "sum_xy": 0.0,
                "na_count": 0,
                "steps": 0,
                "dirty": True,
                "value": math.nan,
            }
            bucket[key] = st
        y = self._wma_parse_sample(self._series_last(series))
        window: deque[Any] = st["window"]
        old: Any = None
        popped = False
        if len(window) == length:
            old = window.popleft()
            popped = True
            if old is None:
                st["na_count"] = int(st["na_count"]) - 1
        window.append(y)
        if y is None:
            st["na_count"] = int(st["na_count"]) + 1
        st["steps"] = int(st["steps"]) + 1
        if len(window) < length:
            st["dirty"] = True
            st["value"] = math.nan
            return math.nan
        if int(st["na_count"]) > 0:
            # Keep skip-na (full interpret ``_builtin_ta_linreg``).
            st["dirty"] = True
            st["value"] = self._linreg_from_valid(window, off)
            return float(st["value"])
        n = float(length)
        reseed = bool(st["dirty"]) or not popped or old is None or (int(st["steps"]) % length == 0)
        if reseed:
            sy = 0.0
            sxy = 0.0
            for k, v in enumerate(window):
                fv = float(v)
                sy += fv
                sxy += float(k) * fv
            st["sum_y"] = sy
            st["sum_xy"] = sxy
            st["dirty"] = False
        else:
            y0 = float(old)
            yn = float(y)
            st["sum_xy"] = float(st["sum_xy"]) - float(st["sum_y"]) + y0 + yn * (n - 1.0)
            st["sum_y"] = float(st["sum_y"]) - y0 + yn
        st["value"] = self._linreg_endpoint(float(st["sum_y"]), float(st["sum_xy"]), length, off)
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
        elif not atr_v:
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

    def _pivot_confirm_window(
        self,
        window: Any,
        left_bars: int,
        right_bars: int,
        *,
        is_high: bool,
    ) -> float | None:
        """Pine ``ta.pivothigh`` / ``ta.pivotlow`` on a chronological window.

        Center is ``right_bars`` before the newest sample. A tie on the left
        still confirms; the right side must be a strict extreme (same rule as
        compile ``numba_pivothigh`` / ``numba_pivotlow``).
        """
        need = left_bars + right_bars + 1
        if len(window) < need:
            return None
        center_i = len(window) - 1 - right_bars
        val = self._finite_or_none(window[center_i])
        if val is None:
            return None
        lo = center_i - left_bars
        hi = center_i + right_bars
        for j in range(lo, hi + 1):
            if j == center_i:
                continue
            other = self._finite_or_none(window[j])
            if other is None:
                continue
            left_side = j < center_i
            if is_high:
                if (other > val) if left_side else (other >= val):
                    return None
            elif (other < val) if left_side else (other <= val):
                return None
        return val

    def _pivothigh_inc_update(
        self,
        series: list[Any],
        left_bars: int,
        right_bars: int,
    ) -> float | None:
        """Incremental pivothigh: left+right confirmation (Pine / compile)."""
        if left_bars < 0 or right_bars < 0:
            return None
        slot = self._ta_next_slot()
        key = ("pivothigh", slot, left_bars, right_bars)
        bucket = self._ta_state_bucket()
        need = left_bars + right_bars + 1
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=max(need, 1)), "n": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        st["window"].append(x)
        st["n"] = int(st["n"]) + 1
        if int(st["n"]) <= left_bars + right_bars:
            st["value"] = None
            return None
        val = self._pivot_confirm_window(st["window"], left_bars, right_bars, is_high=True)
        st["value"] = val
        return val

    def _pivotlow_inc_update(
        self,
        series: list[Any],
        left_bars: int,
        right_bars: int,
    ) -> float | None:
        """Incremental pivotlow: left+right confirmation (Pine / compile)."""
        if left_bars < 0 or right_bars < 0:
            return None
        slot = self._ta_next_slot()
        key = ("pivotlow", slot, left_bars, right_bars)
        bucket = self._ta_state_bucket()
        need = left_bars + right_bars + 1
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=max(need, 1)), "n": 0, "value": None}
            bucket[key] = st
        x = self._series_last(series)
        st["window"].append(x)
        st["n"] = int(st["n"]) + 1
        if int(st["n"]) <= left_bars + right_bars:
            st["value"] = None
            return None
        val = self._pivot_confirm_window(st["window"], left_bars, right_bars, is_high=False)
        st["value"] = val
        return val

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

        Needs ``period`` typical-price samples for the first value (it ranks
        ``period - 1`` directed samples); full ``period`` pairs follow from the
        next bar. Equal TP bars contribute to neither side (reference convention).
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
        if not isinstance(h, (int, float)) or not isinstance(l, (int, float)) or not isinstance(c, (int, float)):
            tps.append(None)
            mfs.append(None)
            st["value"] = math.nan
            return math.nan

        vol = float(v) if isinstance(v, (int, float)) else 0.0
        tp = (float(h) + float(l) + float(c)) / 3.0
        tps.append(tp)
        mfs.append(tp * vol)

        if len(tps) < period:
            st["value"] = math.nan
            return math.nan

        pos = 0.0
        neg = 0.0
        # Last ``pairs`` money-flow samples (each vs previous TP); the first
        # value has ``period - 1`` pairs, then the window is full.
        tp_list = list(tps)
        mf_list = list(mfs)
        pairs = min(period, len(tp_list) - 1)
        for k in range(len(tp_list) - pairs, len(tp_list)):
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
                weights = [math.exp(-((i - m) ** 2) / (2.0 * s * s)) for i in range(length)]
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

        pairs = [(float(x), float(y)) for x, y in zip(wa, wb, strict=False) if x is not None and y is not None]
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
        """Incremental Bollinger Bands ``(middle, upper, lower)``.

        One sliding window shared by SMA (middle) and population stdev
        (ddof=0), matching ``_bollinger_bands`` and reference Pine.
        ``period <= 1`` is na (stdev needs two samples).
        """
        if period <= 1:
            return None, None, None
        bucket, key = self._ta_key1("bb", int(period))
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(), "sum": 0.0, "sumsq": 0.0, "count": 0}
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
            return None, None, None
        s = float(st["sum"])
        ss = float(st["sumsq"])
        var = (ss - (s * s) / n) / n
        var = max(var, 0.0)
        try:
            mid_f = s / period
            dev_f = math.sqrt(var)
            mult = float(multiplier)
        except (TypeError, ValueError):
            return None, None, None
        return mid_f, mid_f + dev_f * mult, mid_f - dev_f * mult

    def _bb_pct_inc_update(
        self,
        series: list[Any],
        period: int,
        multiplier: float,
    ) -> float | None:
        """Incremental %B matching full ``ta.bb_pct`` (clip [0, 100]).

        Derives ``(close - lower) / (upper - lower) * 100`` from the last
        ``_bb_inc_update`` tuple, which already uses reference population
        stdev (ddof=0). ``upper == lower`` → 50.0. ``period <= 1`` is a
        collapsed window (50.0) because ``_bb_inc_update`` is na for stdev.
        One slot every bar, including warmup / na.
        """
        n = int(period)
        if n <= 1:
            # ``_bb_inc_update`` returns without consuming a slot for period<=1.
            self._ta_key1("bb_pct", n)
            if n < 1:
                return None
            x = self._finite_or_none(self._series_last(series))
            if x is None:
                return None
            return 50.0
        mid, upper, lower = self._bb_inc_update(series, n, float(multiplier))
        if upper is None or mid is None or lower is None:
            return None
        if upper == lower:
            return 50.0
        x = self._finite_or_none(self._series_last(series))
        if x is None:
            return None
        bb_pct = ((x - lower) / (upper - lower)) * 100.0
        return max(0.0, min(100.0, bb_pct))

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

    def _aroon_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        length: int,
    ) -> tuple[float, float] | None:
        """Incremental Aroon matching full ``_builtin_ta_aroon`` (down, up).

        Window is ``length + 1`` samples. ``bars_since`` is distance from the
        end of the window; output is ``100 * (length - bars_since) / length``.
        """
        if length <= 0:
            return None
        window_n = length + 1
        slot = self._ta_next_slot()
        key = ("aroon", slot, int(length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "highs": deque(maxlen=window_n),
                "lows": deque(maxlen=window_n),
                "value": None,
            }
            bucket[key] = st
        h = self._series_last(highs)
        l = self._series_last(lows)
        st["highs"].append(h)
        st["lows"].append(l)
        if len(st["highs"]) < window_n or len(st["lows"]) < window_n:
            st["value"] = None
            return None
        h_win = list(st["highs"])
        l_win = list(st["lows"])
        try:
            hh_i = max(range(window_n), key=lambda i: float(h_win[i]))
            ll_i = min(range(window_n), key=lambda i: float(l_win[i]))
        except (TypeError, ValueError):
            st["value"] = None
            return None
        bars_since_hh = (window_n - 1) - hh_i
        bars_since_ll = (window_n - 1) - ll_i
        aroon_up = 100.0 * (length - bars_since_hh) / length
        aroon_down = 100.0 * (length - bars_since_ll) / length
        pair = (float(aroon_down), float(aroon_up))
        st["value"] = pair
        return pair

    def _dpo_inc_update(self, closes: list[Any], length: int) -> float | None:
        """Incremental DPO matching full ``ta.dpo`` last value.

        ``close[length//2 + 1] - sma(close, length)``. SMA uses the same
        last-N mean as the full path (no na-skip).
        """
        if length < 1:
            return None
        slot = self._ta_next_slot()
        key = ("dpo", slot, int(length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        disp = length // 2 + 1
        keep = max(length, disp)
        if st is None:
            st = {"window": deque(maxlen=keep), "value": None}
            bucket[key] = st
        raw = self._series_last(closes)
        try:
            x = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            x = None
        window: deque[float | None] = st["window"]
        window.append(x)
        if len(window) < length:
            st["value"] = None
            return None
        sma_win = list(window)[-length:]
        if x is None or any(v is None for v in sma_win):
            st["value"] = None
            return None
        sma_val = sum(float(v) for v in sma_win) / length
        if len(window) < disp:
            st["value"] = None
            return None
        displaced = list(window)[-disp]
        try:
            dpo_val = float(displaced) - sma_val
        except (TypeError, ValueError):
            st["value"] = None
            return None
        st["value"] = dpo_val
        return dpo_val

    def _donchian_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        length: int,
    ) -> dict[str, float | None]:
        """Incremental Donchian matching full ``ta.donchian`` last window."""
        empty = {"high": None, "low": None, "mid": None}
        if length < 1:
            return empty
        hi = self._highest_inc_update(highs, length)
        lo = self._lowest_inc_update(lows, length)
        if hi is None or lo is None:
            return empty
        try:
            hf = float(hi)
            lf = float(lo)
        except (TypeError, ValueError):
            return empty
        return {"high": hf, "low": lf, "mid": (hf + lf) / 2.0}

    def _kst_inc_update(
        self,
        closes: list[Any],
        length1: int,
        length2: int,
        length3: int,
        length4: int,
    ) -> float | None:
        """Incremental KST matching full ``ta.kst`` last value.

        Full path uses ``(close - close[-length]) / close[-length] * 100``
        (not ``ta.roc``'s ``src[period]`` lookback). Weighted 1/2/3/4, /10.
        """
        lengths = (int(length1), int(length2), int(length3), int(length4))
        if min(lengths) < 1:
            return None
        keep = max(lengths)
        slot = self._ta_next_slot()
        key = ("kst", slot, lengths)
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=keep), "value": None}
            bucket[key] = st
        raw = self._series_last(closes)
        try:
            x = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            x = None
        window: deque[float | None] = st["window"]
        window.append(x)
        if len(window) < keep or x is None:
            st["value"] = None
            return None
        rocs: list[float] = []
        for length in lengths:
            base = window[-length]
            if base is None or x is None:
                st["value"] = None
                return None
            try:
                b = float(base)
                if b == 0.0:
                    rocs.append(0.0)
                else:
                    rocs.append((x - b) / b * 100.0)
            except (TypeError, ValueError):
                st["value"] = None
                return None
        kst_val = (rocs[0] * 1.0 + rocs[1] * 2.0 + rocs[2] * 3.0 + rocs[3] * 4.0) / 10.0
        st["value"] = kst_val
        return kst_val

    def _ichimoku_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        fast_period: int,
        slow_period: int,
        senkou_b_period: int = 52,
    ) -> dict[str, float | None]:
        """Incremental Ichimoku matching full ``ta.ichimoku`` last window.

        Tenkan / kijun / senkou_b are midpoints of highest(high) and
        lowest(low) over ``fast`` / ``slow`` / ``senkou_b_period`` (52).
        Senkou A is the midpoint of tenkan and kijun. The six highest/lowest
        call sites always run so later TA on the same bar keeps its slots.
        """
        empty: dict[str, float | None] = {
            "tenkan_sen": None,
            "kijun_sen": None,
            "senkou_span_a": None,
            "senkou_span_b": None,
        }
        # Always consume six highest/lowest slots, even on warmup / na.
        hi_fast = self._highest_inc_update(highs, fast_period)
        lo_fast = self._lowest_inc_update(lows, fast_period)
        hi_slow = self._highest_inc_update(highs, slow_period)
        lo_slow = self._lowest_inc_update(lows, slow_period)
        hi_b = self._highest_inc_update(highs, senkou_b_period)
        lo_b = self._lowest_inc_update(lows, senkou_b_period)

        def _mid(a: Any, b: Any) -> float | None:
            if a is None or b is None:
                return None
            try:
                return (float(a) + float(b)) / 2.0
            except (TypeError, ValueError):
                return None

        tenkan = _mid(hi_fast, lo_fast)
        kijun = _mid(hi_slow, lo_slow)
        senkou_a = _mid(tenkan, kijun)
        senkou_b = _mid(hi_b, lo_b)
        if tenkan is None and kijun is None and senkou_a is None and senkou_b is None:
            return empty
        return {
            "tenkan_sen": tenkan,
            "kijun_sen": kijun,
            "senkou_span_a": senkou_a,
            "senkou_span_b": senkou_b,
        }

    def _apo_inc_update(self, series: list[Any], fast: int, slow: int) -> float | None:
        """Incremental APO: ``EMA(fast) - EMA(slow)`` matching full ``_apo``.

        Fast EMA then slow EMA every bar so the two call-site slots stay put.
        """
        fast_v = self._ema_inc_update(series, fast)
        slow_v = self._ema_inc_update(series, slow)
        if fast_v is None or slow_v is None:
            return None
        try:
            return float(fast_v) - float(slow_v)
        except (TypeError, ValueError):
            return None

    def _emv_inc_update(
        self,
        highs: list[Any],
        lows: list[Any],
        volumes: list[Any],
        length: int,
    ) -> float | None:
        """Incremental Ease of Movement matching full ``_emv`` last-N valid mean.

        Per-bar sample is na on bar 0, zero volume, or zero box height.
        The SMA skips those na samples (last ``length`` valid values).
        """
        if length < 1:
            return None
        slot = self._ta_next_slot()
        key = ("emv", slot, int(length))
        bucket = self._ta_state_bucket()
        st = bucket.get(key)
        if st is None:
            st = {
                "prev_h": None,
                "prev_l": None,
                "window": deque(maxlen=int(length)),
                "started": False,
                "value": None,
            }
            bucket[key] = st

        def _num(raw: Any) -> float | None:
            if raw is None:
                return None
            try:
                v = float(raw)
            except (TypeError, ValueError):
                return None
            if v != v:
                return None
            return v

        h = _num(self._series_last(highs))
        l = _num(self._series_last(lows))
        vol = _num(self._series_last(volumes))
        if not st["started"]:
            st["started"] = True
            st["prev_h"] = h
            st["prev_l"] = l
            st["value"] = None
            return None

        sample: float | None = None
        prev_h = st["prev_h"]
        prev_l = st["prev_l"]
        if (
            h is not None
            and l is not None
            and prev_h is not None
            and prev_l is not None
            and vol is not None
            and vol != 0.0
        ):
            distance_moved = ((h + l) / 2.0) - ((prev_h + prev_l) / 2.0)
            box_height = h - l
            if box_height != 0.0:
                sample = (distance_moved / box_height) * (h - l) / vol
        if h is not None:
            st["prev_h"] = h
        if l is not None:
            st["prev_l"] = l
        window: deque[float] = st["window"]
        if sample is not None:
            window.append(sample)
        if len(window) < length:
            st["value"] = None
            return None
        emv_sma = sum(window) / length
        st["value"] = emv_sma
        return emv_sma

    def _skewness_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental skewness matching full ``ta.skewness`` last window.

        Population third central moment / std^3 over the last ``period``
        calendar samples. Any non-numeric slot yields na (same as
        ``len(valid_data) < period``). Zero stdev → 0.0. One slot every bar,
        including warmup / na.
        """
        if period < 1:
            return None
        n = int(period)
        bucket, key = self._ta_key1("skewness", n)
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=n), "value": None}
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None = float(raw) if isinstance(raw, (int, float)) else None
        window: deque[float | None] = st["window"]
        window.append(x)
        vals = [v for v in window if v is not None]
        if len(window) < n or len(vals) < n:
            st["value"] = None
            return None
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / n
        std_dev = variance**0.5
        if std_dev == 0.0:
            st["value"] = 0.0
            return 0.0
        skewness_val = sum((v - mean) ** 3 for v in vals) / (n * (std_dev**3))
        st["value"] = skewness_val
        return skewness_val

    def _kurtosis_inc_update(self, series: list[Any], period: int) -> float | None:
        """Incremental excess kurtosis matching full ``ta.kurtosis`` last window.

        ``E[(x-mean)^4] / std^4 - 3`` over the last ``period`` calendar samples.
        Any non-numeric slot yields na. Zero stdev → 0.0. One slot every bar,
        including warmup / na.
        """
        if period < 1:
            return None
        n = int(period)
        bucket, key = self._ta_key1("kurtosis", n)
        st = bucket.get(key)
        if st is None:
            st = {"window": deque(maxlen=n), "value": None}
            bucket[key] = st
        raw = self._series_last(series)
        x: float | None = float(raw) if isinstance(raw, (int, float)) else None
        window: deque[float | None] = st["window"]
        window.append(x)
        vals = [v for v in window if v is not None]
        if len(window) < n or len(vals) < n:
            st["value"] = None
            return None
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / n
        std_dev = variance**0.5
        if std_dev == 0.0:
            st["value"] = 0.0
            return 0.0
        fourth_moment = sum((v - mean) ** 4 for v in vals) / n
        kurtosis_val = (fourth_moment / (std_dev**4)) - 3.0
        st["value"] = kurtosis_val
        return kurtosis_val

    def _beta_inc_update(
        self,
        series1: list[Any],
        series2: list[Any],
        length: int,
    ) -> float | None:
        """Incremental beta matching full ``ta.beta``: cov(s1,s2)/var(s2).

        Two last-N calendar windows. Short window → na; ``var(s2)==0`` → 0.0.
        Non-numeric slots yield na (full path would TypeError on ``sum``).
        One slot every bar, including warmup / na.
        """
        if length < 1:
            return None
        n = int(length)
        bucket, key = self._ta_key1("beta", n)
        st = bucket.get(key)
        if st is None:
            st = {
                "a": deque(maxlen=n),
                "b": deque(maxlen=n),
                "value": None,
            }
            bucket[key] = st
        raw_a = self._series_last(series1)
        raw_b = self._series_last(series2)
        a_v: float | None = float(raw_a) if isinstance(raw_a, (int, float)) else None
        b_v: float | None = float(raw_b) if isinstance(raw_b, (int, float)) else None
        wa: deque[float | None] = st["a"]
        wb: deque[float | None] = st["b"]
        wa.append(a_v)
        wb.append(b_v)
        if len(wa) < n:
            st["value"] = None
            return None
        s1 = list(wa)
        s2 = list(wb)
        if any(v is None for v in s1) or any(v is None for v in s2):
            st["value"] = None
            return None
        mean1 = sum(s1) / n
        mean2 = sum(s2) / n
        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(n)) / n
        variance2 = sum((v - mean2) ** 2 for v in s2) / n
        if variance2 == 0.0:
            st["value"] = 0.0
            return 0.0
        beta_val = covariance / variance2
        st["value"] = beta_val
        return beta_val

    def _r_squared_inc_update(
        self,
        series1: list[Any],
        series2: list[Any],
        length: int,
    ) -> float | None:
        """Incremental r_squared matching full ``ta.r_squared`` last window.

        ``corr(s1,s2)^2`` clipped to [0, 1] over the last-N calendar samples.
        Short window → na; ``var(s1)==0`` or ``var(s2)==0`` → 0.0. Non-numeric
        slots yield na (full path would TypeError on ``sum``). One slot every
        bar, including warmup / na.
        """
        if length < 1:
            return None
        n = int(length)
        bucket, key = self._ta_key1("r_squared", n)
        st = bucket.get(key)
        if st is None:
            st = {
                "a": deque(maxlen=n),
                "b": deque(maxlen=n),
                "value": None,
            }
            bucket[key] = st
        raw_a = self._series_last(series1)
        raw_b = self._series_last(series2)
        a_v: float | None = float(raw_a) if isinstance(raw_a, (int, float)) else None
        b_v: float | None = float(raw_b) if isinstance(raw_b, (int, float)) else None
        wa: deque[float | None] = st["a"]
        wb: deque[float | None] = st["b"]
        wa.append(a_v)
        wb.append(b_v)
        if len(wa) < n:
            st["value"] = None
            return None
        s1 = list(wa)
        s2 = list(wb)
        if any(v is None for v in s1) or any(v is None for v in s2):
            st["value"] = None
            return None
        mean1 = sum(s1) / n
        mean2 = sum(s2) / n
        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(n)) / n
        var1 = sum((v - mean1) ** 2 for v in s1) / n
        var2 = sum((v - mean2) ** 2 for v in s2) / n
        if var1 == 0.0 or var2 == 0.0:
            st["value"] = 0.0
            return 0.0
        correlation = covariance / ((var1 * var2) ** 0.5)
        r_squared = correlation**2
        r_sq_clipped = max(0.0, min(1.0, r_squared))
        st["value"] = r_sq_clipped
        return r_sq_clipped

    def _comovement_inc_update(
        self,
        series1: list[Any],
        series2: list[Any],
        length: int,
    ) -> float | None:
        """Incremental comovement matching full ``ta.comovement`` last window.

        Percent of bars ``1..N-1`` where Δs1 and Δs2 share sign
        (product > 0). Short window → na; ``length==1`` → 0.0. Non-numeric
        slots yield na (full path would TypeError on subtraction). One slot
        every bar, including warmup / na.
        """
        if length < 1:
            return None
        n = int(length)
        bucket, key = self._ta_key1("comovement", n)
        st = bucket.get(key)
        if st is None:
            st = {
                "a": deque(maxlen=n),
                "b": deque(maxlen=n),
                "value": None,
            }
            bucket[key] = st
        raw_a = self._series_last(series1)
        raw_b = self._series_last(series2)
        a_v: float | None = float(raw_a) if isinstance(raw_a, (int, float)) else None
        b_v: float | None = float(raw_b) if isinstance(raw_b, (int, float)) else None
        wa: deque[float | None] = st["a"]
        wb: deque[float | None] = st["b"]
        wa.append(a_v)
        wb.append(b_v)
        if len(wa) < n:
            st["value"] = None
            return None
        s1 = list(wa)
        s2 = list(wb)
        if any(v is None for v in s1) or any(v is None for v in s2):
            st["value"] = None
            return None
        if n <= 1:
            st["value"] = 0.0
            return 0.0
        same_direction = sum(1 for i in range(1, n) if (s1[i] - s1[i - 1]) * (s2[i] - s2[i - 1]) > 0)
        como_val = (same_direction / (n - 1)) * 100.0
        st["value"] = como_val
        return como_val

    def _volume_weighted_momentum_inc_update(
        self,
        series: list[Any],
        volume: list[Any],
        length: int,
    ) -> float | None:
        """Incremental volume-weighted momentum matching the full last-N path.

        Last-N ``(Δprice * vol) / sum(vol)``. Short window → na; ``volume_sum``
        of 0 → 0.0. Non-numeric volume is 0.0 (full path); non-numeric price
        yields na. One slot every bar, including warmup / na. Price deque is
        N+1 so the oldest Δprice still has a previous sample once history
        is long enough; the full path breaks that last term when
        ``len(series)==length``.
        """
        n = int(length)
        bucket, key = self._ta_key1("volume_weighted_momentum", n)
        if n < 1:
            return None
        st = bucket.get(key)
        if st is None:
            st = {
                "p": deque(maxlen=n + 1),
                "v": deque(maxlen=n),
                "value": None,
            }
            bucket[key] = st
        raw_p = self._series_last(series)
        raw_v = self._series_last(volume)
        p_v: float | None = float(raw_p) if isinstance(raw_p, (int, float)) else None
        v_v: float | None = float(raw_v) if isinstance(raw_v, (int, float)) else None
        wp: deque[float | None] = st["p"]
        wv: deque[float | None] = st["v"]
        wp.append(p_v)
        wv.append(v_v)
        if len(wv) < n:
            st["value"] = None
            return None
        ps = list(wp)
        vs = list(wv)
        momentum_sum = 0.0
        volume_sum = 0.0
        for i in range(n):
            p_end = len(ps) - 1 - i
            p_prev = p_end - 1
            if p_prev < 0:
                break
            pv = ps[p_end]
            pp = ps[p_prev]
            if pv is None or pp is None:
                st["value"] = None
                return None
            vol_raw = vs[len(vs) - 1 - i]
            vol = 0.0 if vol_raw is None else vol_raw
            momentum_sum += (pv - pp) * vol
            volume_sum += vol
        val = momentum_sum / volume_sum if volume_sum > 0 else 0.0
        st["value"] = val
        return val

    def _cumulative_delta_inc_update(
        self,
        close: list[Any],
        volume: list[Any],
        period: int,
    ) -> float:
        """Incremental last-N signed volume matching full ``ta.cumulative_delta``.

        ``+vol`` if close>prev, ``-vol`` if close<prev, 0 if equal. Non-numeric
        close/volume treated as 0 (full path). Window short or ``period<=0``
        → 0.0. One slot every bar, including warmup / na.
        """
        n = int(period)
        bucket, key = self._ta_key1("cumulative_delta", n)
        if n <= 0:
            return 0.0
        st = bucket.get(key)
        if st is None:
            st = {
                "c": deque(maxlen=n + 1),
                "v": deque(maxlen=n),
                "count": 0,
                "value": 0.0,
            }
            bucket[key] = st
        raw_c = self._series_last(close)
        raw_v = self._series_last(volume)
        # Keep None for non-numeric close so prev-na skips the signed bar
        # (full path uses current as prev when close[i-1] is non-numeric).
        c_v: float | None = float(raw_c) if isinstance(raw_c, (int, float)) else None
        v_v: float = float(raw_v) if isinstance(raw_v, (int, float)) else 0.0
        wc: deque[float | None] = st["c"]
        wv: deque[float] = st["v"]
        wc.append(c_v)
        wv.append(v_v)
        st["count"] = int(st["count"]) + 1
        if st["count"] < n:
            st["value"] = 0.0
            return 0.0
        cs = list(wc)
        vs = list(wv)
        delta = 0.0
        offset = len(cs) - len(vs)
        for j in range(len(vs)):
            c_idx = offset + j
            c_raw = cs[c_idx]
            c = 0.0 if c_raw is None else c_raw
            prev_raw = None if c_idx == 0 else cs[c_idx - 1]
            c_prev = c if prev_raw is None else prev_raw
            v = vs[j]
            if c > c_prev:
                delta += v
            elif c < c_prev:
                delta -= v
        st["value"] = delta
        return delta

    def _volume_momentum_inc_update(
        self,
        volume: list[Any],
        period: int,
    ) -> float:
        """Incremental volume momentum matching full ``ta.volume_momentum``.

        ROC of the period-SMA of numeric volume: last-N vs the previous last-N
        (shifted by 1). Non-numeric samples are dropped (full path). Window
        short or ``period<=0`` → 0.0; old SMA == 0 → 0.0; result clipped to
        [-100, 100]. One slot every bar, including warmup / na.
        """
        n = int(period)
        bucket, key = self._ta_key1("volume_momentum", n)
        if n <= 0:
            return 0.0
        st = bucket.get(key)
        if st is None:
            st = {
                "w": deque(maxlen=n + 1),
                "value": 0.0,
            }
            bucket[key] = st
        raw_v = self._series_last(volume)
        w: deque[float] = st["w"]
        if isinstance(raw_v, (int, float)):
            w.append(float(raw_v))
        if len(w) < n + 1:
            st["value"] = 0.0
            return 0.0
        vols = list(w)
        old_vol = sum(vols[:-1]) / n
        new_vol = sum(vols[-n:]) / n
        if old_vol == 0:
            st["value"] = 0.0
            return 0.0
        momentum = ((new_vol - old_vol) / old_vol) * 100.0
        val = max(-100.0, min(100.0, momentum))
        st["value"] = val
        return val

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
        # Duck-type PineSeries first (dominant Runtime arg). Checking
        # ``history`` before ``isinstance(..., Sequence)`` skips the ABC
        # cache on every full-recompute materialization.
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
                # Fingerprint the two newest samples (`is`) — small ints are
                # interned, so one sample cannot distinguish two series.
                head2 = hist[1] if take > 1 else None
                cache = getattr(self, "_pine_as_series_cache", None)
                if cache is None:
                    cache = {}
                    self._pine_as_series_cache = cache  # type: ignore[attr-defined]
                key = id(value)
                ent = cache.get(key)
                if ent is not None and ent[0] == n and ent[1] is head and ent[2] is head2 and ent[3] == take:
                    return ent[4]
                # Newest-first → take first `take` then reverse to chronological.
                # Avoid list(reversed(full_history)) when n >> SERIES_MAX.
                if take == n:
                    raw = list(reversed(hist))
                else:
                    # hist[0] newest … hist[take-1] oldest among window
                    raw = [hist[i] for i in range(take - 1, -1, -1)]
                cache[key] = (n, head, head2, take, raw)
                return raw
        # ChronoTailView (oldest-first Sequence, no .history)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            try:
                return self._cap_series_list(list(value))
            except TypeError:
                pass
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
        if series_map.get(name):
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
        try:
            series_map = self.current_series
        except AttributeError:
            return []
        if not series_map:
            return []
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
        self._require_len(args, BINARY, "Function takes two series arguments")
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
        acc = 0.0
        for i, v in enumerate(window):
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:  # NaN
                return None
            acc += fv * (i + 1)
        return acc / (period * (period + 1) / 2.0)

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
        """Standard deviation over period (strict window, reference Pine).

        Any ``na`` in the last ``period`` samples yields ``na``. Reference
        ``ta.stdev`` is the **population** standard deviation (ddof=0), so the
        sum of squared deviations is divided by ``period``, not ``period - 1``.
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
        return statistics.pstdev(vals)

    def _tr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        handle_na: bool = False,
    ) -> list[float | None]:
        """True Range calculation (na-safe).

        ``handle_na=True`` seeds bar 0 with ``high - low`` (reference
        ``ta.tr(true)``); the default leaves bar 0 as ``na``.
        """
        if not closes:
            return []
        if handle_na and highs and lows:
            try:
                first = float(highs[0]) - float(lows[0])
            except (TypeError, ValueError):
                first = None
        else:
            first = None
        result: list[float | None] = [first]
        for idx in range(1, len(closes)):
            h, l, c_prev = (
                highs[idx] if idx < len(highs) else None,
                lows[idx] if idx < len(lows) else None,
                closes[idx - 1],
            )
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
        if prev is not None and prev[0] is not None and prev[1] is not None and a_f is not None and b_f is not None:
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

        ``period`` pairwise steps (``s[-1] < s[-2] < …``), needing
        ``period+1`` samples — matches ``numba_falling`` (``i >= length``).
        Any Pine na (None) or non-numeric sample → False (never TypeError).
        """
        if period < 1 or len(series) < period + 1:
            return False
        for idx in range(1, period + 1):
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

        ``period`` pairwise steps, needing ``period+1`` samples — matches
        ``numba_rising``. Any na / non-numeric → False (never TypeError).
        """
        if period < 1 or len(series) < period + 1:
            return False
        for idx in range(1, period + 1):
            a, b = series[-idx], series[-idx - 1]
            if a is None or b is None:
                return False
            try:
                if float(a) <= float(b):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _highestbars(self, series: list[float], period: int) -> int | None:
        """Offset to highest value in period (na-safe; matches ``_highestbars_inc_update``).

        Returns bars-back offset of the extreme (0 = current bar is highest).
        Skips None / non-numeric; all-na or short window → ``na``.
        On ties prefers the **newest** extreme in the window (rightmost).
        """
        if period < 1 or len(series) < period:
            return None
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
            if best_v is None or fv >= best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            return None
        return -(period - 1 - best_i)

    def _lowestbars(self, series: list[float], period: int) -> int | None:
        """Offset to lowest value in period (na-safe; matches ``_lowestbars_inc_update``).

        Same na / non-numeric / all-na contract as :meth:`_highestbars`.
        """
        if period < 1 or len(series) < period:
            return None
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
            if best_v is None or fv <= best_v:
                best_v = fv
                best_i = i
        if best_i is None:
            return None
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
