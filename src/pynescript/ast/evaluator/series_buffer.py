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
(wrapper + ``current_series`` lists) is the status quo in ``backend/runtime.py``.

This module is the single-buffer alternative, gated by env ``PYNE_SERIES_RING``
(default **off** — ``0`` / unset / empty). When off, hosts keep using
``backend.series.PineSeries`` unchanged.

Optional ``maxlen`` composes with T1 (``_SERIES_MAX`` / ``max_bars_back``): the
ring drops oldest samples so memory stays bounded without fighting Agent 03's
``current_series`` cap (which still owns the host lists path).
"""

from __future__ import annotations

import operator
import os

from collections.abc import Callable, Iterator, Sequence
from typing import Any


def series_ring_enabled() -> bool:
    """True when ``PYNE_SERIES_RING`` is an explicit truthy flag.

    Default **off**. Accepted on values: ``1``, ``true``, ``yes``, ``on``
    (case-insensitive). Anything else (including unset) → False.
    """
    v = os.environ.get("PYNE_SERIES_RING", "0").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _coerce_pine_offset(index: Any) -> int | None:
    """Normalize a Pine history offset; return ``None`` for na / invalid."""
    t = type(index)
    if t is int:
        # bool is int subclass — treat as 0/1 offset
        return int(index)
    if t is float:
        if index != index:  # NaN
            return None
        return int(index)
    if index is None:
        return None
    try:
        return int(index)
    except (TypeError, ValueError):
        return None


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
            raise TypeError("history indices must be integers")
        if index < 0:
            index += len(self._buf)
        if index < 0 or index >= len(self._buf):
            raise IndexError("history index out of range")
        # newest-first: view[0] == current == lookback(0)
        return self._buf.lookback(index)

    def __iter__(self) -> Iterator[Any]:
        n = len(self._buf)
        for i in range(n):
            yield self._buf.lookback(i)

    def __reversed__(self) -> Iterator[Any]:
        # reversed(newest-first) → chronological (oldest first)
        yield from self._buf

    def __repr__(self) -> str:
        return f"NewestFirstHistoryView(len={len(self._buf)})"


class RingPineSeries:
    """PineSeries-compatible wrapper over :class:`ChronologicalSeriesBuffer`.

    Public surface matches ``backend.series.PineSeries`` for Runtime / TA duck
    typing:

    - ``.current`` — scalar current bar
    - ``.history`` — newest-first view (legacy reverse paths keep working)
    - ``.update(v)`` — push bar
    - ``series[n]`` — O(1) lookback via chronological storage
    - arithmetic ops on ``.current`` with na-safe ``None``

    Extra:

    - ``.buffer`` — underlying chronological ring
    - ``chrono_order = True`` — migration marker for ``_as_series`` zero-copy
    """

    __slots__ = ("buffer", "history", "current")
    __hash__ = None  # type: ignore[assignment]
    chrono_order: bool = True

    def __init__(self, initial_value: Any = None, history_length: int = 1000) -> None:
        # history_length mirrors PineSeries maxlen; treat <=0 as uncapped.
        maxlen: int | None
        if history_length is None or history_length <= 0:  # type: ignore[comparison-overlap]
            maxlen = None
        else:
            maxlen = max(1, int(history_length))
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

    def __getitem__(self, index: Any) -> Any:
        """``series[0]`` current, ``series[1]`` previous; OOB/na → ``None``."""
        return self.buffer[index]

    def _binary_op(self, other: Any, op: Callable[..., Any]) -> Any:
        other_val = other.current if isinstance(other, (RingPineSeries,)) else other
        # Also accept legacy PineSeries without importing backend (duck-type).
        if other_val is other and hasattr(other, "current") and type(other).__name__ in {
            "PineSeries",
            "RingPineSeries",
        }:
            other_val = other.current
        if self.current is None or other_val is None:
            return None
        return op(self.current, other_val)

    def __add__(self, other: Any) -> Any:
        return self._binary_op(other, operator.add)

    def __sub__(self, other: Any) -> Any:
        return self._binary_op(other, operator.sub)

    def __mul__(self, other: Any) -> Any:
        return self._binary_op(other, operator.mul)

    def __truediv__(self, other: Any) -> Any:
        return self._binary_op(other, operator.truediv)

    def __floordiv__(self, other: Any) -> Any:
        return self._binary_op(other, operator.floordiv)

    def __mod__(self, other: Any) -> Any:
        return self._binary_op(other, operator.mod)

    def __pow__(self, other: Any) -> Any:
        return self._binary_op(other, operator.pow)

    def __radd__(self, other: Any) -> Any:
        return self._binary_op(other, lambda a, b: operator.add(b, a))

    def __rsub__(self, other: Any) -> Any:
        return self._binary_op(other, lambda a, b: operator.sub(b, a))

    def __rmul__(self, other: Any) -> Any:
        return self._binary_op(other, lambda a, b: operator.mul(b, a))

    def __rtruediv__(self, other: Any) -> Any:
        return self._binary_op(other, lambda a, b: operator.truediv(b, a))

    def __eq__(self, other: Any) -> Any:
        return self._binary_op(other, operator.eq)

    def __ne__(self, other: Any) -> Any:
        return self._binary_op(other, operator.ne)

    def __lt__(self, other: Any) -> Any:
        return self._binary_op(other, operator.lt)

    def __le__(self, other: Any) -> Any:
        return self._binary_op(other, operator.le)

    def __gt__(self, other: Any) -> Any:
        return self._binary_op(other, operator.gt)

    def __ge__(self, other: Any) -> Any:
        return self._binary_op(other, operator.ge)

    def __bool__(self) -> bool:
        return bool(self.current)

    def __str__(self) -> str:
        return str(self.current)

    def __repr__(self) -> str:
        return f"RingPineSeries({self.current})"


def make_series(
    initial_value: Any = None,
    history_length: int = 1000,
    *,
    force_ring: bool | None = None,
) -> Any:
    """Construct a series wrapper honouring ``PYNE_SERIES_RING``.

    When the flag is off (default), returns legacy ``backend.series.PineSeries``
    so behaviour is bit-identical to the pre-Phase-2.2 path.

    Prefer ``backend.series.make_pine_series`` from Runtime hosts; this helper
    is for evaluator-side / unit tests that already import this module.

    Parameters
    ----------
    force_ring:
        Override env: ``True`` → always ring, ``False`` → always legacy,
        ``None`` → read env.
    """
    use_ring = series_ring_enabled() if force_ring is None else force_ring
    if use_ring:
        return RingPineSeries(initial_value, history_length=history_length)
    # Lazy import avoids circular load when only the buffer type is needed.
    from backend.series import PineSeries

    return PineSeries(initial_value, history_length=history_length)
