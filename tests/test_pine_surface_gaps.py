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

"""Regression tests for remaining TV v6 surface gaps closed 2026-07-25."""

from __future__ import annotations

import pytest

from backend.runtime import Runtime
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import Box
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.evaluator.builtins.drawing import LineFill
from tests.fixtures.parity.ohlcv import OHLCV


@pytest.fixture(autouse=True)
def _reset_drawings():
    DrawingRegistry.reset()
    yield
    DrawingRegistry.reset()


def test_ta_alma_bbw_cmo_correlation():
    e = NodeLiteralEvaluator()
    series = list(range(1, 21))
    m = e._build_builtin_map()
    alma = m["ta.alma"]([series, 9])
    assert alma is not None and isinstance(alma, float)
    bbw = m["ta.bbw"]([series, 10, 2.0])
    assert bbw is not None and bbw > 0
    cmo = m["ta.cmo"]([series, 9])
    assert cmo is not None
    corr = m["ta.correlation"]([series, [x * 2 for x in series], 10])
    assert corr is not None and abs(corr - 1.0) < 1e-9


def test_linefill_and_line_get_price():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    l1 = m["line.new"]([0, 0.0, 10, 10.0])
    l2 = m["line.new"]([0, 5.0, 10, 15.0])
    fill = m["linefill.new"]([l1, l2, "#00ff00"])
    assert isinstance(fill, LineFill)
    assert m["linefill.get_line1"]([fill]) is l1
    assert m["linefill.get_line2"]([fill]) is l2
    price = m["line.get_price"]([l1, 5])
    assert price == pytest.approx(5.0)


def test_box_text_and_table_setters():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    box = m["box.new"]([0, 10.0, 5, 1.0])
    assert isinstance(box, Box)
    m["box.set_text"]([box, "hello"])
    m["box.set_text_color"]([box, "#fff"])
    m["box.set_text_wrap"]([box, "auto"])
    assert box.text == "hello"
    assert box.text_color == "#fff"
    assert box.text_wrap == "auto"

    table = m["table.new"](["top_right", 2, 2])
    m["table.set_position"]([table, "bottom_left"])
    m["table.set_bgcolor"]([table, "#111"])
    m["table.cell"]([table, 0, 0, "A"])
    m["table.cell_set_width"]([table, 0, 0, 50])
    m["table.cell_set_tooltip"]([table, 0, 0, "tip"])
    assert table.position == "bottom_left"
    assert table.bgcolor == "#111"
    cell = table.cells[(0, 0)]
    assert cell.width == 50
    assert cell.tooltip == "tip"


def test_strategy_risk_and_max_bars_back_and_ticker_inherit():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    m["strategy.risk.max_drawdown"]([20.0])
    m["strategy.risk.max_cons_loss_days"]([3])
    m["strategy.risk.allow_entry_in"](["long"])
    assert e._strategy_state.max_drawdown_risk == 20.0
    assert e._strategy_state.max_cons_loss_days == 3
    assert e._strategy_state.allow_entry_in == "long"

    m["max_bars_back"](["close", 500])
    assert e._max_bars_back_decls[-1]["num"] == 500

    t = m["ticker.inherit"](["BINANCE:BTCUSDT"])
    assert t.symbol == "BINANCE:BTCUSDT"


def test_runtime_plot_is_bar_scalar():
    src = """//@version=6
indicator("sma plot")
plot(ta.sma(close, 5))
"""
    result = Runtime().run(src, OHLCV)
    assert "error" not in result
    plots = result["plots"]
    assert len(plots) == len(OHLCV)
    # later bars should be numeric scalars, not nested lists
    for v in plots[-10:]:
        assert v is None or isinstance(v, (int, float))


def test_footprint_volume_row_accessors():
    from pynescript.ast.evaluator.builtins.request import Footprint
    from pynescript.ast.evaluator.builtins.request import VolumeRow

    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    row = VolumeRow(up_price=101, down_price=100, buy_volume=10, sell_volume=4, delta=6, is_imbalance=True)
    fp = Footprint(buy_volume=10, sell_volume=4, delta=6, total_volume=14, rows=[row], poc_row=row)
    assert m["footprint.total_volume"]([fp]) == 14
    assert m["footprint.rows"]([fp]) == [row]
    assert m["footprint.get_row_by_price"]([fp, 100.5]) is row
    assert m["volume_row.buy_volume"]([row]) == 10
    assert m["volume_row.has_buy_imbalance"]([row]) is True
    assert m["volume_row.has_sell_imbalance"]([row]) is False
