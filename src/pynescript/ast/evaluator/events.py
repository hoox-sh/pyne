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

"""Strategy event capture primitives.

A :class:`StrategyEvent` is the structured representation of one
``strategy.*`` call emitted during Pine script execution. The shape is the
parity contract between the Python reference implementation (this repo) and
the TypeScript port in ``pine-worker`` (Plan 2 of
``.opencode/plans/2026-07-05-pine-worker-strategy-events.md``). Any change
to this dataclass must be reflected in
``pine-worker/src/evaluator/events.ts`` and the parity test corpus under
``tests/fixtures/parity/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# Literal aliases for static type checking and IDE support. Runtime values
# are not enforced — the dispatch layer in ``strategy.py`` is responsible
# for emitting only valid kinds.
StrategyEventKind = Literal[
    "entry",
    "exit",
    "close",
    "close_all",
    "cancel",
    "cancel_all",
    "order",
]
StrategyDirection = Literal["long", "short"]
StrategyOrderType = Literal["market", "limit", "stop"]


@dataclass(frozen=True)
class StrategyEvent:
    """A single ``strategy.*`` call, captured at the bar it was emitted.

    The dataclass is frozen so events are immutable once recorded; the
    runtime consumes them via :meth:`to_dict` for serialization to the
    trade-worker boundary (Plan 3).
    """

    kind: StrategyEventKind
    id: str | None
    direction: StrategyDirection | None
    qty: float | None
    order_type: StrategyOrderType | None
    limit: float | None
    stop: float | None
    oca_name: str | None
    comment: str | None
    # Context fields — filled by the runtime at emit time, not by the
    # builtin. The dispatch layer is responsible for setting these from
    # the per-bar loop state.
    bar_index: int
    bar_time: int
    ohlc: tuple[float, float, float, float]
    script_id: str
    run_id: str

    def to_dict(self) -> dict:
        """Serialize the event to a plain dict.

        Every field is included, with ``None`` preserved for unspecified
        fields (the parity contract with the TS port requires the key to
        always be present).

        Manual construction (not ``dataclasses.asdict``) — asdict walks fields
        via reflection and dominates warm strategy event drains.
        """
        ohlc = self.ohlc
        return {
            "kind": self.kind,
            "id": self.id,
            "direction": self.direction,
            "qty": self.qty,
            "order_type": self.order_type,
            "limit": self.limit,
            "stop": self.stop,
            "oca_name": self.oca_name,
            "comment": self.comment,
            "bar_index": self.bar_index,
            "bar_time": self.bar_time,
            # tuple → list for JSON / parity round-trip
            "ohlc": [ohlc[0], ohlc[1], ohlc[2], ohlc[3]],
            "script_id": self.script_id,
            "run_id": self.run_id,
        }
