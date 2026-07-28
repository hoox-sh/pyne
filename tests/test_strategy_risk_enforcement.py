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

"""strategy.risk.* gates are enforced at entry time."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator


def test_allow_entry_in_blocks_opposite_side():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    m["strategy.risk.allow_entry_in"](["long"])
    m["strategy.entry"](["L", "long", 1.0])
    assert e._strategy_state.position_direction == "long"
    # short blocked
    m["strategy.entry"](["S", "short", 1.0])
    assert e._strategy_state.position_direction == "long"
    blocked = [ev for ev in e._strategy_state._events if ev.comment == "risk_blocked"]
    assert blocked


def test_max_position_size_caps_qty():
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    # 1% of 100k equity at price 100 => max qty 10
    m["strategy.risk.max_position_size"]([1.0])
    m["strategy.entry"](["L", "long", 1000.0])
    assert e._strategy_state.position_size == 10.0


def test_max_drawdown_blocks_further_entries():
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 1}
    m = e._build_builtin_map()
    m["strategy.risk.max_drawdown"]([50.0])  # absolute
    # Force drawdown state
    e._strategy_state._equity_peak = 100_000.0
    e._strategy_state._max_drawdown = 100.0  # already exceeded 50
    m["strategy.entry"](["L", "long", 1.0])
    assert e._strategy_state.position_direction == "flat"
    assert e._strategy_state.entries_blocked is True


def test_bar_mode_sma_returns_scalar():
    e = NodeLiteralEvaluator()
    e._pine_bar_mode = True
    m = e._build_builtin_map()
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    val = m["ta.sma"]([series, 3])
    assert isinstance(val, float)
    assert val == 4.0  # (3+4+5)/3


def test_list_mode_sma_returns_series():
    e = NodeLiteralEvaluator()
    # default: not bar mode
    m = e._build_builtin_map()
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    val = m["ta.sma"]([series, 3])
    assert isinstance(val, list)
    assert val == [None, None, 2.0, 3.0, 4.0]
