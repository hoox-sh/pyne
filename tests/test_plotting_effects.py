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

"""Real plotting effects: all plot* / hline / bgcolor / barcolor / fill register."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.plotting import Plot
from pynescript.ast.evaluator.builtins.plotting import PlotRegistry
from pynescript.ast.helper import parse


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class TestPlottingEffects:
    def setup_method(self) -> None:
        PlotRegistry.reset()

    def test_plot_registers_and_returns_plot_id(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        result = _eval(ev, "plot(close, title='c', color=color.blue, linewidth=2)")
        assert isinstance(result, Plot)
        assert len(PlotRegistry.plots) == 1
        assert PlotRegistry.plots[0].title == "c"
        assert PlotRegistry.plots[0].linewidth == 2
        assert PlotRegistry.plots[0].kind == "plot"

    def test_hline_bgcolor_barcolor_register(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        h = _eval(ev, "hline(50, title='mid', color=color.gray)")
        assert isinstance(h, Plot)
        assert h.kind == "hline"
        assert h.price == 50 or h.series == 50
        _eval(ev, "bgcolor(color.red, title='bg')")
        _eval(ev, "barcolor(color.green)")
        kinds = {p.kind for p in PlotRegistry.plots}
        assert "hline" in kinds
        assert "bgcolor" in kinds
        assert "barcolor" in kinds
        assert len(PlotRegistry.plots) == 3

    def test_fill_registers_with_plot_refs(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        ev.evaluate_script(
            """
p1 = plot(close, title='a')
p2 = plot(open, title='b')
fill(p1, p2, color=color.blue, title='f')
"""
        )
        fills = [p for p in PlotRegistry.plots if p.kind == "fill"]
        assert len(fills) == 1
        assert fills[0].title == "f"
        assert fills[0].plot1 is not None
        assert fills[0].plot2 is not None

    def test_plotshape_plotchar_plotarrow_register(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        _eval(ev, "plotshape(true, title='s')")
        _eval(ev, "plotchar(true, title='ch', char='X')")
        _eval(ev, "plotarrow(1.0, title='ar')")
        kinds = {p.kind for p in PlotRegistry.plots}
        assert "plotshape" in kinds
        assert "plotchar" in kinds
        assert "plotarrow" in kinds
        assert len(PlotRegistry.plots) == 3

    def test_plotbar_and_plotcandle_register(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        _eval(ev, "plotbar(open, high, low, close, title='bars')")
        _eval(ev, "plotcandle(open, high, low, close, title='candles')")
        assert len(PlotRegistry.plots) == 2
        titles = {p.title for p in PlotRegistry.plots}
        assert "bars" in titles
        assert "candles" in titles

    def test_plot_linestyle_kwargs(self) -> None:
        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        p = _eval(ev, "plot(close, linestyle=plot.linestyle_dashed)")
        assert isinstance(p, Plot)
        assert p.linestyle in ("linestyle_dashed", "dashed") or "dash" in str(p.linestyle)

    def test_default_titles_for_visual_kinds(self) -> None:
        """Default title strings must stay stable for dual-mode series keys."""
        from pynescript.ast.evaluator.builtins.plotting import DEFAULT_VISUAL_TITLES

        ev = NodeLiteralEvaluator()
        PlotRegistry.reset()
        _eval(ev, "bgcolor(color.red)")
        _eval(ev, "plotshape(true)")
        _eval(ev, "plotchar(true)")
        _eval(ev, "hline(1)")
        _eval(ev, "plotarrow(1.0)")
        by_kind = {p.kind: p.title for p in PlotRegistry.plots}
        assert by_kind["bgcolor"] == DEFAULT_VISUAL_TITLES["bgcolor"]
        assert by_kind["plotshape"] == DEFAULT_VISUAL_TITLES["plotshape"]
        assert by_kind["plotchar"] == DEFAULT_VISUAL_TITLES["plotchar"]
        assert by_kind["hline"] == DEFAULT_VISUAL_TITLES["hline"]
        assert by_kind["plotarrow"] == DEFAULT_VISUAL_TITLES["plotarrow"]
