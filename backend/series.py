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

"""Pine series value type + host OHLCV list cap policy (T1).

``PineSeries`` is newest-first (``history[0]`` == current). Host Runtime keeps
separate chronological ``current_series`` lists for ``ta.*`` helpers; those
lists are optionally capped to ``max_bars_back`` / ``_SERIES_MAX`` so long
charts do not grow O(bars) memory per series.

**Flag:** ``PYNE_SERIES_CAP`` — default **ON** (``1``). Set ``0`` / ``false`` /
``no`` / ``off`` to disable host list trimming (oracle / debug). Cap size
defaults to :data:`DEFAULT_SERIES_MAX` (256), raised by script
``max_bars_back`` when larger, or overridden by ``PYNE_SERIES_MAX``.

**Flag:** ``PYNE_SERIES_RING`` — default **OFF** (``0``). Set ``1`` / ``true`` /
``yes`` / ``on`` to use chronological ring storage (``RingPineSeries``) via
:func:`make_pine_series` for O(1) Pine lookback. Orthogonal to the list cap
(T1); does not replace ``current_series`` trimming.

**Min history for correctness (periods ≤ cap):**

- ``ta.sma(src, p)`` / ``highest`` / ``lowest`` / window kernels: need
  **p** samples in the window → safe when ``p ≤ cap``.
- Recursive smoothers under **incremental** TA (default): state carries forward;
  only the last sample is required per bar → safe independent of list length
  once warm.
- Recursive smoothers under **full recompute** (``PYNE_TA_INCREMENTAL=0``):
  EMA/RMA restart from the capped window each bar and can diverge from a
  full-history oracle when ``bars ≫ cap``. Prefer incremental TA (default).

Out-of-range history offsets always return ``None`` (``na``); never ``0``.
"""

from __future__ import annotations

import operator
import os
import re

from collections import deque
from collections.abc import Callable, Sequence
from typing import Any

# Aligns with evaluator TechnicalMixin._SERIES_MAX (TA materialization window).
DEFAULT_SERIES_MAX = 256
# Amortize in-place prefix deletes: grow to keep+slack, then drop back to keep.
SERIES_CAP_SLACK = 64
# PineSeries maxlen floor (historical host default). List caps (T1) may be
# smaller (_SERIES_MAX); indexing ``close[n]`` keeps this floor unless
# max_bars_back / PYNE_SERIES_MAX raises it.
DEFAULT_PINESERIES_HISTORY = 1000

# indicator(..., max_bars_back=500) / strategy("t", max_bars_back = 300)
_MAX_BARS_BACK_RE = re.compile(
    r"\bmax_bars_back\s*=\s*(\d+)\b",
    re.IGNORECASE,
)


def series_cap_enabled() -> bool:
    """Whether Runtime should trim append-only ``current_series`` lists.

    Env ``PYNE_SERIES_CAP``: default **on**. Disable with ``0`` / ``false`` /
    ``no`` / ``off`` (empty string also disables for explicit unset-in-tests
    only when set to those tokens — missing env → on).
    """
    raw = os.environ.get("PYNE_SERIES_CAP")
    if raw is None:
        return True
    v = raw.strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("",):
        # Explicit empty → treat as default ON (same as missing).
        return True
    return True


def env_series_max() -> int | None:
    """Optional absolute cap from ``PYNE_SERIES_MAX`` (positive int)."""
    raw = os.environ.get("PYNE_SERIES_MAX", "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n > 0 else None


def parse_max_bars_back_from_source(source: str) -> int | None:
    """Best-effort scan for ``max_bars_back = N`` in script source.

    Covers ``indicator`` / ``strategy`` kwargs and standalone
    ``max_bars_back(series, N)`` call sites that use a literal N as the
    second argument form is harder; the assignment form is the common
    declaration path.
    """
    if not source:
        return None
    found: int | None = None
    for m in _MAX_BARS_BACK_RE.finditer(source):
        try:
            n = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        if found is None or n > found:
            found = n
    return found


def resolve_series_cap(
    *,
    series_max: int | None = None,
    max_bars_back: int | None = None,
    default: int = DEFAULT_SERIES_MAX,
) -> int:
    """Resolve host OHLCV list / PineSeries history depth.

    Precedence:

    1. ``PYNE_SERIES_MAX`` env (absolute override)
    2. ``max(base, max_bars_back)`` where *base* is *series_max* or *default*
    """
    env = env_series_max()
    if env is not None:
        return max(1, env)
    base = int(series_max) if series_max and int(series_max) > 0 else int(default)
    if max_bars_back is not None:
        try:
            mbb = int(max_bars_back)
        except (TypeError, ValueError):
            mbb = 0
        if mbb > base:
            base = mbb
    return max(1, base)


def series_cap_limit(keep: int, slack: int = SERIES_CAP_SLACK) -> int:
    """Length at which lists are trimmed back to *keep*."""
    k = max(1, int(keep))
    s = max(0, int(slack))
    return k + s


def trim_series_lists(
    lists: Sequence[list[Any]],
    *,
    keep: int,
    slack: int = SERIES_CAP_SLACK,
    length_hint: int | None = None,
) -> int:
    """In-place prefix trim of chronological lists (oldest first).

    When length exceeds ``keep + slack``, drop the oldest
    ``length - keep`` samples via ``del lst[:drop]`` so pre-bound list
    refs (and ``evaluator.current_series``) stay valid. Amortized O(1)
    per bar with slack; no rebind.

    Returns the (possibly reduced) common length after the call.
    """
    k = max(1, int(keep))
    limit = series_cap_limit(k, slack)
    if not lists:
        return 0
    n = length_hint if length_hint is not None else len(lists[0])
    if n <= limit:
        return n
    drop = n - k
    if drop <= 0:
        return n
    for lst in lists:
        # Guard short / desynced lists (should not happen on host path).
        if len(lst) > k:
            del lst[: min(drop, len(lst) - k)]
    return k


def pineseries_history_length(
    *,
    cap_enabled: bool | None = None,
    series_cap: int | None = None,
) -> int:
    """History maxlen for host-built :class:`PineSeries` instances.

    Never smaller than :data:`DEFAULT_PINESERIES_HISTORY` so existing
    ``close[n]`` scripts (n ≤ 999) keep working. Raised when the resolved
    list cap (``max_bars_back`` / ``PYNE_SERIES_MAX``) is larger.
    """
    floor = DEFAULT_PINESERIES_HISTORY
    if series_cap is not None:
        try:
            sc = int(series_cap)
        except (TypeError, ValueError):
            sc = 0
        if sc > floor:
            return sc
    return floor


def series_ring_enabled() -> bool:
    """``PYNE_SERIES_RING`` explicit on (default **off**).

    When on, :func:`make_pine_series` returns a chronological ring buffer
    (``RingPineSeries``) with O(1) lookback. Orthogonal to T1
    ``PYNE_SERIES_CAP`` / ``current_series`` list trimming.
    """
    v = os.environ.get("PYNE_SERIES_RING", "0").strip().lower()
    return v in {"1", "true", "yes", "on"}


def make_pine_series(
    initial_value: Any = None,
    history_length: int = DEFAULT_PINESERIES_HISTORY,
) -> Any:
    """Factory for host OHLCV series wrappers.

    Default (``PYNE_SERIES_RING`` off): classic :class:`PineSeries`
    (newest-first deque / ``appendleft``).

    Flag on: chronological ring (``RingPineSeries``) — same public
    ``.current`` / ``.history`` / ``.update`` / ``[n]`` surface; lookback
    is O(1) via reverse-index into oldest-first storage. Does **not**
    replace ``current_series`` list caps (Agent 03 / T1).
    """
    if series_ring_enabled():
        from pynescript.ast.evaluator.series_buffer import RingPineSeries

        return RingPineSeries(initial_value, history_length=history_length)
    return PineSeries(initial_value, history_length=history_length)


class PineSeries:
    """
    Represents a Pine Script series variable.
    Effectively behaves like the 'current value' (scalar) for math operations,
    but supports indexing [x] to access historical values.

    History is **newest-first** (``history[0]`` == current bar == ``series[0]``).
    Out-of-range offsets return ``None`` (Pine ``na``); never invent ``0``.
    """

    __slots__ = ("history", "current")
    __hash__ = None  # type: ignore

    def __init__(self, initial_value: Any = None, history_length: int = DEFAULT_PINESERIES_HISTORY):
        # Start empty so TA history is not polluted by a leading None placeholder
        hl = max(1, int(history_length)) if history_length else DEFAULT_PINESERIES_HISTORY
        self.history: deque = deque(maxlen=hl)
        self.current = initial_value
        if initial_value is not None:
            self.history.appendleft(initial_value)

    @property
    def history_length(self) -> int | None:
        """Configured deque maxlen (``None`` if unbounded — not used by host)."""
        return self.history.maxlen

    def set_history_length(self, history_length: int) -> None:
        """Resize history buffer, keeping the newest samples (newest-first order)."""
        hl = max(1, int(history_length))
        if self.history.maxlen == hl:
            return
        # deque has no maxlen setter; rebuild preserving newest-first order.
        items = list(self.history)
        if len(items) > hl:
            items = items[:hl]
        self.history = deque(items, maxlen=hl)

    def update(self, new_value: Any) -> None:
        """Push a new value for the current bar."""
        self.current = new_value
        self.history.appendleft(new_value)

    def set_current(self, new_value: Any) -> None:
        """Overwrite the current-bar sample without pushing history.

        Used when Pine does ``x = 0.0`` then ``x := expr`` on the same bar so
        ``x[1]`` remains the previous bar's final value (not the intermediate).
        """
        self.current = new_value
        if self.history:
            self.history[0] = new_value
        else:
            self.history.appendleft(new_value)

    def __getitem__(self, index: int):
        """Access historical values. series[0] is current, series[1] is previous.

        Float offsets are truncated toward zero (TV coerces length-like floats).
        ``na`` / non-numeric / negative / OOB index → ``None`` (na), not a crash.
        """
        t = type(index)
        if t is not int:
            if t is float:
                if index != index:  # NaN
                    return None
                index = int(index)
            elif index is None:
                return None
            else:
                try:
                    index = int(index)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None
        # Negative offsets are invalid Pine history refs. Soft-fail to na so
        # warm-up / for-to with auto step -1 / highestbars(-n) misuse do not
        # abort the bar loop (TV-like indicator residual behaviour).
        if index < 0:
            return None
        hist = self.history
        if index >= len(hist):
            return None  # na — past available history (warmup / lookback)
        return hist[index]

    def _binary_op(self, other: Any, op: Callable) -> Any:
        other_val = other.current if isinstance(other, PineSeries) else other

        if self.current is None or other_val is None:
            return None

        return op(self.current, other_val)

    # Arithmetic Operations
    def __add__(self, other):
        return self._binary_op(other, operator.add)

    def __sub__(self, other):
        return self._binary_op(other, operator.sub)

    def __mul__(self, other):
        return self._binary_op(other, operator.mul)

    def __truediv__(self, other):
        return self._binary_op(other, operator.truediv)

    def __floordiv__(self, other):
        return self._binary_op(other, operator.floordiv)

    def __mod__(self, other):
        return self._binary_op(other, operator.mod)

    def __pow__(self, other):
        return self._binary_op(other, operator.pow)

    # Reverse Arithmetic
    def __radd__(self, other):
        return self._binary_op(other, lambda a, b: operator.add(b, a))

    def __rsub__(self, other):
        return self._binary_op(other, lambda a, b: operator.sub(b, a))

    def __rmul__(self, other):
        return self._binary_op(other, lambda a, b: operator.mul(b, a))

    def __rtruediv__(self, other):
        return self._binary_op(other, lambda a, b: operator.truediv(b, a))

    # Comparison
    def __eq__(self, other):
        return self._binary_op(other, operator.eq)

    def __ne__(self, other):
        return self._binary_op(other, operator.ne)

    def __lt__(self, other):
        return self._binary_op(other, operator.lt)

    def __le__(self, other):
        return self._binary_op(other, operator.le)

    def __gt__(self, other):
        return self._binary_op(other, operator.gt)

    def __ge__(self, other):
        return self._binary_op(other, operator.ge)

    # Boolean
    def __bool__(self):
        return bool(self.current)

    def __str__(self):
        return str(self.current)

    def __repr__(self):
        return f"PineSeries({self.current})"


def estimate_series_bytes(n_bars: int, n_lists: int = 6) -> int:
    """Rough lower bound for chronological list storage (pointers only).

    Useful in tests / docs: capped host stores ~``cap * n_lists`` slots
    instead of ``n_bars * n_lists``.
    """
    # CPython list pointer ~8 bytes on 64-bit; ignore object payload.
    return max(0, int(n_bars)) * max(0, int(n_lists)) * 8
