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

"""Chronological series buffer with O(1) Pine lookback (Phase 2.2).

Pine indexing is an *offset from the current bar*, not a Python list index:

- ``series[0]`` — current bar
- ``series[1]`` — one bar ago
- ``series[n]`` — n bars ago
- OOB / negative / ``na`` → ``None`` (never invent ``0``)

Storage layout (PineTS-style): **chronological** (oldest first, newest last).
Lookback maps offset ``n`` → physical index ``-(n + 1)`` in O(1).

Legacy ``PineSeries`` stores a newest-first ``deque`` via ``appendleft``. That
makes lookback ``hist[n]`` O(1) at the ends but forces TA helpers to
``list(reversed(history))`` for chronological materialization. Dual storage
(wrapper + ``current_series`` lists) is the status quo in
``pynescript.runtime.host``.

This module is the single-buffer alternative, gated by env ``PYNE_SERIES_RING``
(default **off** — ``0`` / unset / empty). When on, Runtime binds
``current_series`` to :class:`ChronoTailView` over the ring (last ``keep``
samples) and does **not** dual-write append-only lists.

Optional ``maxlen`` composes with T1 (``_SERIES_MAX`` / ``max_bars_back``): the
ring drops oldest samples so memory stays bounded without fighting Agent 03's
``current_series`` cap (which still owns the host lists path).

``RingPineSeries`` constructor *history_length* matches ``PineSeries``
(``0`` / ``None`` → 1000, negative → 1) — never uncapped-on-zero.
``series[n]`` OOB / negative / ``na`` / ``inf`` → ``None`` (never ``0``).
"""

from __future__ import annotations

import operator

from collections.abc import Iterator, Sequence
from typing import Any

from pynescript.runtime.series import (
    DEFAULT_PINESERIES_HISTORY,
    PineSeries,
    _coerce_pine_offset,
    _normalize_history_length,
    pineseries_history_length,
    series_ring_enabled,
)

__all__ = [
    "ChronoTailView",
    "ChronologicalSeriesBuffer",
    "NewestFirstHistoryView",
    "RingPineSeries",
    "evaluator_history_length",
    "make_series",
    "series_ring_enabled",
]


class ChronologicalSeriesBuffer:
    """Oldest-first series storage with O(1) Pine offset lookback.

    Parameters
    ----------
    maxlen:
        Optional hard cap. When set, the buffer is a fixed-capacity modular
        ring: append overwrites the oldest slot after fill. ``None`` grows
        unbounded (plain list append — still O(1) lookback).
    """

    __slots__ = ("_data", "_start", "_len", "maxlen")
    # Marker for hosts / ``_as_series`` migration (chrono, not newest-first).
    chrono_order: bool = True

    def __init__(self, maxlen: int | None = None) -> None:
        """Create an empty buffer; *maxlen* caps ring capacity (``None`` = grow).

        Raises:
            ValueError: If *maxlen* is not positive when provided.
        """
        if maxlen is not None and maxlen <= 0:
            msg = f"maxlen must be positive or None, got {maxlen!r}"
            raise ValueError(msg)
        self.maxlen = maxlen
        if maxlen is None:
            self._data: list[Any] = []
            self._start = 0
            self._len = 0
        else:
            self._data = [None] * maxlen
            self._start = 0
            self._len = 0

    def __len__(self) -> int:
        return self._len

    def clear(self) -> None:
        """Drop all samples; keep ring capacity when ``maxlen`` is set."""
        if self.maxlen is None:
            self._data.clear()
        else:
            # Keep capacity; logical length only.
            self._start = 0
        self._len = 0

    def append(self, value: Any) -> None:
        """Push a new bar sample (newest)."""
        maxlen = self.maxlen
        if maxlen is None:
            self._data.append(value)
            self._len = len(self._data)
            return
        data = self._data
        n = self._len
        if n < maxlen:
            data[(self._start + n) % maxlen] = value
            self._len = n + 1
            return
        # Full: overwrite oldest, advance start.
        data[self._start] = value
        self._start = (self._start + 1) % maxlen

    def update(self, value: Any) -> None:
        """Alias for :meth:`append` (PineSeries API symmetry)."""
        self.append(value)

    @property
    def current(self) -> Any:
        """Newest sample, or ``None`` if empty."""
        if self._len == 0:
            return None
        return self.lookback(0)

    def lookback(self, offset: int) -> Any:
        """Return sample at Pine offset ``offset`` (0 = current).

        O(1). Out of range / negative → ``None`` (na).
        """
        if offset < 0:
            return None
        n = self._len
        if offset >= n:
            return None
        maxlen = self.maxlen
        if maxlen is None:
            # Chronological list: newest at -1.
            return self._data[-(offset + 1)]
        # Modular ring: physical index of newest is start+len-1.
        idx = (self._start + n - 1 - offset) % maxlen
        return self._data[idx]

    def __getitem__(self, index: Any) -> Any:
        off = _coerce_pine_offset(index)
        if off is None:
            return None
        return self.lookback(off)

    def chronological(self) -> list[Any]:
        """Materialize oldest→newest list (copy). Prefer for TA windows."""
        n = self._len
        if n == 0:
            return []
        maxlen = self.maxlen
        if maxlen is None:
            return list(self._data)
        data = self._data
        start = self._start
        return [data[(start + i) % maxlen] for i in range(n)]

    def __iter__(self) -> Iterator[Any]:
        """Iterate oldest → newest."""
        n = self._len
        maxlen = self.maxlen
        if maxlen is None:
            yield from self._data
            return
        data = self._data
        start = self._start
        for i in range(n):
            yield data[(start + i) % maxlen]

    def __repr__(self) -> str:
        return f"ChronologicalSeriesBuffer(len={self._len}, maxlen={self.maxlen})"


class ChronoTailView(Sequence[Any]):
    """Oldest-first view of the last *keep* samples in a chronological buffer.

    Used as ``evaluator.current_series`` when ``PYNE_SERIES_RING`` is on so
    ``ta.*`` named lookups see the same cap window as T1 list trim without
    a second append-only list. ``[0]`` is the oldest sample still in the
    window; ``[-1]`` is the current bar.
    """

    __slots__ = ("_buf", "_keep")

    def __init__(self, buf: ChronologicalSeriesBuffer, keep: int) -> None:
        if keep < 1:
            msg = f"keep must be >= 1, got {keep!r}"
            raise ValueError(msg)
        self._buf = buf
        self._keep = int(keep)

    def __len__(self) -> int:
        n = len(self._buf)
        k = self._keep
        return n if n <= k else k

    def __getitem__(self, index: int | slice) -> Any:
        n = len(self)
        if isinstance(index, slice):
            start, stop, step = index.indices(n)
            return [self[i] for i in range(start, stop, step)]
        if type(index) is not int:
            try:
                index = operator.index(index)
            except (TypeError, ValueError):
                raise TypeError("tail indices must be integers") from None
        if index < 0:
            index += n
        if index < 0 or index >= n:
            raise IndexError("tail index out of range")
        # chronological window: index 0 = oldest kept, n-1 = current
        return self._buf.lookback(n - 1 - index)

    def __iter__(self) -> Iterator[Any]:
        n = len(self)
        buf = self._buf
        for i in range(n):
            yield buf.lookback(n - 1 - i)

    def __repr__(self) -> str:
        return f"ChronoTailView(len={len(self)}, keep={self._keep})"


class NewestFirstHistoryView(Sequence[Any]):
    """Present chronological storage as newest-first ``history`` for duck-types.

    Legacy helpers assume ``history[0]`` is the current bar and
    ``list(reversed(history))`` yields chronological order (see
    ``TechnicalHelpers._as_series``). This view keeps that contract without
    copying on every index.
    """

    __slots__ = ("_buf",)

    def __init__(self, buf: ChronologicalSeriesBuffer) -> None:
        self._buf = buf

    def __len__(self) -> int:
        return len(self._buf)

    def __getitem__(self, index: int | slice) -> Any:
        if isinstance(index, slice):
            n = len(self._buf)
            # Materialize slice in newest-first order.
            return [self._buf.lookback(i) for i in range(*index.indices(n))]
        if type(index) is not int:
            try:
                index = operator.index(index)
            except (TypeError, ValueError):
                raise TypeError("history indices must be integers") from None
        if index < 0:
            index += len(self._buf)
        if index < 0 or index >= len(self._buf):
            raise IndexError("history index out of range")
        # newest-first: view[0] == current == lookback(0)
        return self._buf.lookback(index)

    def __setitem__(self, index: int, value: Any) -> None:
        """Overwrite a newest-first slot (deque ``history[0] = v`` parity)."""
        if type(index) is not int:
            try:
                index = operator.index(index)
            except (TypeError, ValueError):
                raise TypeError("history indices must be integers") from None
        n = len(self._buf)
        if index < 0:
            index += n
        if index < 0 or index >= n:
            raise IndexError("history index out of range")
        buf = self._buf
        maxlen = buf.maxlen
        if maxlen is None:
            buf._data[-(index + 1)] = value
        else:
            buf._data[(buf._start + buf._len - 1 - index) % maxlen] = value

    def appendleft(self, value: Any) -> None:
        """Push a new newest sample (``deque.appendleft`` parity)."""
        self._buf.append(value)

    def __iter__(self) -> Iterator[Any]:
        n = len(self._buf)
        for i in range(n):
            yield self._buf.lookback(i)

    def __reversed__(self) -> Iterator[Any]:
        # reversed(newest-first) → chronological (oldest first)
        yield from self._buf

    def __repr__(self) -> str:
        return f"NewestFirstHistoryView(len={len(self._buf)})"


class RingPineSeries(PineSeries):
    """PineSeries-compatible wrapper over :class:`ChronologicalSeriesBuffer`.

    Public surface matches ``backend.series.PineSeries`` for Runtime / TA duck
    typing (subclass so ``isinstance(..., PineSeries)`` stays true):

    - ``.current`` — scalar current bar
    - ``.history`` — newest-first view (legacy reverse paths keep working)
    - ``.update(v)`` — push bar
    - ``series[n]`` — O(1) lookback via chronological storage
    - arithmetic ops on ``.current`` with na-safe ``None``

    Extra:

    - ``.buffer`` — underlying chronological ring
    - ``chrono_order = True`` — migration marker for ``_as_series`` zero-copy

    *history_length* uses the same policy as :class:`PineSeries`
    (falsy → 1000, negative → 1). Does **not** call ``PineSeries.__init__``
    (that would allocate a newest-first deque).
    """

    __slots__ = ("buffer",)
    chrono_order: bool = True

    def __init__(
        self,
        initial_value: Any = None,
        history_length: int = DEFAULT_PINESERIES_HISTORY,
    ) -> None:
        """Create a series; seed with *initial_value* when not ``None``."""
        # Do not call PineSeries.__init__ — no newest-first deque.
        maxlen = _normalize_history_length(history_length)
        self.buffer = ChronologicalSeriesBuffer(maxlen=maxlen)
        self.history = NewestFirstHistoryView(self.buffer)
        self.current = initial_value
        if initial_value is not None:
            self.buffer.append(initial_value)
            self.current = initial_value

    @property
    def history_length(self) -> int | None:
        """Configured ring capacity (``None`` if uncapped)."""
        return self.buffer.maxlen

    def set_history_length(self, history_length: int) -> None:
        """Resize ring, keeping the newest samples (API parity with PineSeries)."""
        hl = max(1, int(history_length))
        if self.buffer.maxlen == hl:
            return
        # Rebuild from chronological materialization of newest `hl` samples.
        chrono = self.buffer.chronological()
        if len(chrono) > hl:
            chrono = chrono[-hl:]
        new_buf = ChronologicalSeriesBuffer(maxlen=hl)
        for v in chrono:
            new_buf.append(v)
        self.buffer = new_buf
        self.history = NewestFirstHistoryView(new_buf)

    def update(self, new_value: Any) -> None:
        """Push a new value for the current bar."""
        self.current = new_value
        self.buffer.append(new_value)

    def set_current(self, new_value: Any) -> None:
        """Overwrite the current-bar sample without pushing history.

        Same-bar ``x = 0.0`` / ``x := expr`` must not create an extra history
        slot (``x[1]`` should be the prior bar's final value).
        """
        self.current = new_value
        buf = self.buffer
        n = buf._len
        if n <= 0:
            buf.append(new_value)
            return
        maxlen = buf.maxlen
        if maxlen is None:
            buf._data[-1] = new_value
        else:
            idx = (buf._start + n - 1) % maxlen
            buf._data[idx] = new_value

    def __getitem__(self, index: Any) -> Any:
        """``series[0]`` current, ``series[1]`` previous; OOB/na/inf → ``None``."""
        return self.buffer[index]

    def __repr__(self) -> str:
        return f"RingPineSeries({self.current})"


def evaluator_history_length(evaluator: Any = None) -> int:
    """Maxlen for evaluator-created series (user vars, call-expr buffers).

    Matches host OHLCV :func:`~pynescript.runtime.series.pineseries_history_length`
    so ``x[600]`` and ``close[600]`` share the same floor (1000) and the same
    raised cap when ``max_bars_back`` / ``PYNE_SERIES_MAX`` is larger.
    """
    cap = getattr(evaluator, "_pine_series_cap", None) if evaluator is not None else None
    return pineseries_history_length(series_cap=cap)


def make_series(
    initial_value: Any = None,
    history_length: int = DEFAULT_PINESERIES_HISTORY,
    *,
    force_ring: bool | None = None,
) -> Any:
    """Construct a series wrapper honouring ``PYNE_SERIES_RING``.

    When the flag is off (default), returns legacy
    ``pynescript.runtime.series.PineSeries`` so behaviour is bit-identical to
    the pre-Phase-2.2 path.

    Prefer ``pynescript.runtime.make_pine_series`` from Runtime hosts; this
    helper is for evaluator-side / unit tests that already import this module.

    Parameters
    ----------
    force_ring:
        Override env: ``True`` → always ring, ``False`` → always legacy,
        ``None`` → read env.
    """
    use_ring = series_ring_enabled() if force_ring is None else force_ring
    if use_ring:
        return RingPineSeries(initial_value, history_length=history_length)
    return PineSeries(initial_value, history_length=history_length)
