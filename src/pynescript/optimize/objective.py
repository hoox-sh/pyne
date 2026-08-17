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

"""Scalar objectives over :class:`StrategyStats`."""

from __future__ import annotations

import math

from pynescript.optimize.types import ObjectiveId
from pynescript.optimize.types import StrategyStats

REJECT = float("-inf")


def score_stats(
    stats: StrategyStats | None,
    objective: ObjectiveId = "composite",
    *,
    min_trades: int = 5,
) -> float:
    """Return a higher-is-better score, or ``-inf`` when the trial is invalid."""
    if stats is None:
        return REJECT
    if stats.trades < max(0, int(min_trades)):
        return REJECT
    if objective == "net_pnl":
        return float(stats.total_pnl)
    if objective == "profit_factor":
        pf = float(stats.profit_factor)
        if not math.isfinite(pf):
            return 1.0e6 if pf > 0 else REJECT
        return pf
    if objective == "calmar":
        dd = max(float(stats.max_dd), 1e-9)
        return float(stats.total_pnl) / dd
    # composite — penalise low trade count and deep drawdown
    pnl = float(stats.total_pnl)
    trades = max(int(stats.trades), 1)
    dd = max(float(stats.max_dd), 0.0)
    sign = 1.0 if pnl >= 0 else -1.0
    return sign * abs(pnl) * math.sqrt(trades) / (1.0 + dd)


def parse_objective(raw: str | None) -> ObjectiveId:
    """Normalize a user/API objective name."""
    s = (raw or "composite").strip().lower().replace(" ", "_")
    aliases = {
        "pnl": "net_pnl",
        "net": "net_pnl",
        "profit": "net_pnl",
        "pf": "profit_factor",
        "profitfactor": "profit_factor",
        "dd": "calmar",
        "calmar_like": "calmar",
    }
    s = aliases.get(s, s)
    if s not in {"net_pnl", "profit_factor", "calmar", "composite"}:
        raise ValueError(f"unknown objective: {raw!r}")
    return s  # type: ignore[return-value]
