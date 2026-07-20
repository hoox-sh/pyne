# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Strategy runtime depth: open trades, equity stats, multi-bar golden scripts."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse


def _eval_expr(ev: NodeLiteralEvaluator, source: str):
    return ev.visit(parse(source, mode="eval").body)


def _set_bar(ev: NodeLiteralEvaluator, bar_index: int, close: float, time: int | None = None) -> None:
    ev.context["bar_index"] = bar_index
    ev.context["close"] = close
    ev.context["open"] = close
    ev.context["high"] = close
    ev.context["low"] = close
    ev.context["time"] = time if time is not None else 1_700_000_000_000 + bar_index * 60_000


class TestStrategySeriesVariables:
    """strategy.position_size / opentrades / netprofit resolve as values, not strings."""

    def test_flat_defaults(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        assert _eval_expr(ev, "strategy.position_size") == 0.0
        assert _eval_expr(ev, "strategy.opentrades") == 0
        assert _eval_expr(ev, "strategy.closedtrades") == 0
        assert _eval_expr(ev, "strategy.netprofit") == 0.0
        assert _eval_expr(ev, "strategy.openprofit") == 0.0
        assert _eval_expr(ev, "strategy.equity") == _eval_expr(ev, "strategy.initial_capital")

    def test_long_entry_updates_position_and_opentrades(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 5, 100.0, time=12345)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")

        assert _eval_expr(ev, "strategy.position_size") == 2.0
        assert _eval_expr(ev, "strategy.position_avg_price") == 100.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades") == 0
        assert _eval_expr(ev, "strategy.opentrades.entry_price(0)") == 100.0
        assert _eval_expr(ev, "strategy.opentrades.size(0)") == 2.0
        assert _eval_expr(ev, "strategy.opentrades.entry_bar_index(0)") == 5
        assert _eval_expr(ev, "strategy.opentrades.entry_time(0)") == 12345

    def test_short_entry_uses_negative_position_size(self) -> None:
        """Pine: strategy.position_size is negative when short."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 50.0)
        _eval_expr(ev, "strategy.entry('S', strategy.short, 3.0)")
        assert _eval_expr(ev, "strategy.position_size") == -3.0
        assert _eval_expr(ev, "strategy.opentrades") == 1

    def test_openprofit_tracks_mark_to_market(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")
        _set_bar(ev, 1, 110.0)
        # 2 * (110 - 100) = 20
        assert _eval_expr(ev, "strategy.openprofit") == 20.0
        equity0 = _eval_expr(ev, "strategy.initial_capital")
        assert _eval_expr(ev, "strategy.equity") == equity0 + 20.0

    def test_close_realizes_netprofit_and_clears_open(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")
        _set_bar(ev, 3, 110.0)
        _eval_expr(ev, "strategy.close('L')")

        assert _eval_expr(ev, "strategy.position_size") == 0.0
        assert _eval_expr(ev, "strategy.opentrades") == 0
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.netprofit") == 20.0
        assert _eval_expr(ev, "strategy.openprofit") == 0.0
        assert _eval_expr(ev, "strategy.closedtrades.profit(0)") == 20.0
        assert _eval_expr(ev, "strategy.closedtrades.exit_price(0)") == 110.0
        assert _eval_expr(ev, "strategy.closedtrades.exit_bar_index(0)") == 3

    def test_partial_close_keeps_remaining_open_trade(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 4.0)")
        _set_bar(ev, 1, 105.0)
        _eval_expr(ev, "strategy.close('L', 1.0)")  # close 1 of 4

        assert _eval_expr(ev, "strategy.position_size") == 3.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.netprofit") == 5.0  # 1 * 5
        assert _eval_expr(ev, "strategy.opentrades.size(0)") == 3.0


class TestStrategyWinLossStats:
    def test_win_and_loss_trade_counts(self) -> None:
        ev = NodeLiteralEvaluator()
        # Win: long 100 -> 110
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L1', strategy.long, 1.0)")
        _set_bar(ev, 1, 110.0)
        _eval_expr(ev, "strategy.close('L1')")
        # Loss: long 110 -> 100
        _eval_expr(ev, "strategy.entry('L2', strategy.long, 1.0)")
        _set_bar(ev, 2, 100.0)
        _eval_expr(ev, "strategy.close('L2')")

        assert _eval_expr(ev, "strategy.closedtrades") == 2
        assert _eval_expr(ev, "strategy.wintrades") == 1
        assert _eval_expr(ev, "strategy.losstrades") == 1
        assert _eval_expr(ev, "strategy.grossprofit") == 10.0
        assert _eval_expr(ev, "strategy.grossloss") == 10.0
        assert _eval_expr(ev, "strategy.netprofit") == 0.0


class TestStrategyGoldenMultiBar:
    """Simple multi-bar script: buy bar 0, sell bar 2, inspect series."""

    def test_entry_exit_over_bars_via_script_statements(self) -> None:
        # Simulate bar-by-bar evaluation of a tiny strategy body.
        body_entry = "strategy.entry('L', strategy.long, 1.0)"
        body_exit = "strategy.close('L')"
        read = """
strategy.position_size
"""
        ev = NodeLiteralEvaluator()
        prices = [100.0, 102.0, 108.0]

        sizes: list[float] = []
        for i, px in enumerate(prices):
            _set_bar(ev, i, px)
            if i == 0:
                _eval_expr(ev, body_entry)
            elif i == 2:
                _eval_expr(ev, body_exit)
            sizes.append(float(_eval_expr(ev, "strategy.position_size")))

        assert sizes == [1.0, 1.0, 0.0]
        assert _eval_expr(ev, "strategy.netprofit") == 8.0  # 108 - 100
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.equity") == _eval_expr(ev, "strategy.initial_capital") + 8.0

    def test_full_script_string_single_bar_snapshot(self) -> None:
        """Evaluate a strategy script once with context prices (single bar fill)."""
        src = """//@version=6
strategy("Golden")
strategy.entry("L", strategy.long, 1.0)
"""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 42.0)
        ev.evaluate_script(src)
        assert _eval_expr(ev, "strategy.position_size") == 1.0
        assert _eval_expr(ev, "strategy.position_avg_price") == 42.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
