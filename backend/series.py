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

from __future__ import annotations

import operator

from collections import deque
from collections.abc import Callable
from typing import Any


class PineSeries:
    """
    Represents a Pine Script series variable.
    Effectively behaves like the 'current value' (scalar) for math operations,
    but supports indexing [x] to access historical values.
    """

    __hash__ = None  # type: ignore

    def __init__(self, initial_value: Any = None, history_length: int = 1000):
        # Start empty so TA history is not polluted by a leading None placeholder
        self.history: deque = deque(maxlen=history_length)
        self.current = initial_value
        if initial_value is not None:
            self.history.appendleft(initial_value)

    def update(self, new_value: Any):
        """Push a new value for the current bar."""
        self.current = new_value
        self.history.appendleft(new_value)

    def __getitem__(self, index: int):
        """Access historical values. series[0] is current, series[1] is previous."""
        if index < 0:
            msg = "Pine Script does not support negative indexing"
            raise ValueError(msg)
        if index >= len(self.history):
            return None  # na
        return self.history[index]

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
