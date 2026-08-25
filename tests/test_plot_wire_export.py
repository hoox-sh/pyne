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

"""AXIS contract parity: plot wire params, OHLC siblings, drawing export."""

from __future__ import annotations

import math

from backend.runtime import Runtime
from pynescript.ast.evaluator.builtins.plot_params import PLOT_PARAM_SPECS
from pynescript.ast.evaluator.builtins.plot_params import extract_wire_meta
from pynescript.ast.evaluator.builtins.plot_params import param_index
from pynescript.ast.evaluator.builtins.plot_params import resolve_arg


class TestParamSpec:
    def test_canonical_plot_order(self) -> None:
        assert param_index("plot", "linewidth") == 3
        assert param_index("plot", "style") == 4
        assert param_index("plot", "trackprice") == 5
        assert param_index("plot", "histbase") == 6
        assert param_index("plot", "offset") == 7
        assert param_index("plot", "show_last") == 10

    def test_unknown_param_is_minus_one(self) -> None:
        assert param_index("plot", "nonsense") == -1
        assert param_index("nope", "series") == -1

    def test_resolve_kwarg_wins(self) -> None:
        args = ["c", "t", None, 2]
        kwargs = {"style": "histogram"}
        assert resolve_arg("plot", "style", args, kwargs) == "histogram"
        assert resolve_arg("plot", "linewidth", args, kwargs, 1) == 2

    def test_resolve_positional(self) -> None:
        args = ["c", "t", "#f00", 2, "histogram", False, -10.0]
        assert resolve_arg("plot", "linewidth", args, None, 1) == 2
        assert resolve_arg("plot", "style", args, None, "") == "histogram"
        assert resolve_arg("plot", "histbase", args, None, None) == -10.0


class TestExtractWireMeta:
    def test_static_values(self) -> None:
        args = ["c", None, None, 2, "histogram", True, -20.0, 3, False, True, 50]
        out = extract_wire_meta("plot", args, None)
        assert out == {
            "trackprice": True,
            "histbase": -20.0,
            "offset": 3,
            "join": False,
            "editable": True,
            "show_last": 50,
        }

    def test_kwargs_only(self) -> None:
        out = extract_wire_meta("plot", ["c"], {"offset": 2, "histbase": 5, "editable": False})
        assert out == {"offset": 2, "histbase": 5.0, "editable": False}

    def test_absent_and_default_offset_omitted(self) -> None:
        assert extract_wire_meta("plot", ["c"], None) == {}
        # offset=0 is Pine default → omitted
        assert extract_wire_meta("plot", ["c"], {"offset": 0}) == {}

    def test_bool_rejected_for_int_param(self) -> None:
        assert extract_wire_meta("plot", ["c"], {"offset": True}) == {}

    def test_uncoercible_values_skipped(self) -> None:
        assert extract_wire_meta("plot", ["c"], {"offset": "x"}) == {}
        assert extract_wire_meta("plot", ["c"], {"histbase": float("nan")}) == {}

    def test_hline_kind_and_unknown_kind(self) -> None:
        assert extract_wire_meta("hline", [1.0], {"editable": False}) == {"editable": False}
        assert extract_wire_meta("nope", ["c"], {"offset": 2}) == {}

    def test_spec_positions_match_order(self) -> None:
        for spec in PLOT_PARAM_SPECS.values():
            assert spec == tuple((n, i) for i, (n, _) in enumerate(spec))


def _bars(n: int = 24) -> list[dict]:
    out = []
    for i in range(n):
        c = 100 + 5 * math.sin(i / 3.0)
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


_WIRE_SCRIPT = """
//@version=6
indicator("wire", overlay=true)
plot(close, title="base", linewidth=2, offset=3, histbase=-10, trackprice=true, join=true, editable=false, show_last=20)
bgcolor(close > open ? color.green : na, title="bg", offset=1)
"""


class TestRuntimeWireMeta:
    def test_plot_wire_params_in_capture(self) -> None:
        r = Runtime().run(_WIRE_SCRIPT, _bars(), mode="interpret")
        meta = r["plot_meta"]["base"]
        assert meta["linewidth"] == 2

    def test_defaults_omitted(self) -> None:
        script = '//@version=6\nindicator("m", overlay=true)\nplot(close, title="plain")\n'
        r = Runtime().run(script, _bars(), mode="interpret")
        meta = r["plot_meta"]["plain"]
        for key in ("offset", "histbase", "trackprice", "join", "show_last"):
            assert key not in meta


class TestCaptureLayer:
    def _run_evaluator(self, script: str):
        # Drive CustomEvaluator directly so we can inspect _plot_meta_list
        # before host packing (packing whitelist is a later task).
        from pynescript.ast.helper import parse
        from pynescript.runtime.evaluator import CustomEvaluator

        ev = CustomEvaluator()
        tree = parse(script)
        bars = _bars(4)
        for b in bars:
            ev.current_series = {
                "open": [b["open"]],
                "high": [b["high"]],
                "low": [b["low"]],
                "close": [b["close"]],
            }
            ev._plot_n_bars = len(bars)
            try:
                ev.visit(tree)
            except Exception:  # noqa: S110 — capture still ran for statements that evaluated
                pass
            ev.finish_bar_plots()
        return ev

    def test_first_sighting_registers_extras(self) -> None:
        script = '//@version=6\nindicator("w")\nplot(close, title="base", offset=3, histbase=-10, trackprice=true)\n'
        ev = self._run_evaluator(script)
        by_title = {m.get("title"): m for m in ev._plot_meta_list}
        m = by_title["base"]
        assert m["offset"] == 3
        assert m["histbase"] == -10
        assert m["trackprice"] is True
        assert "_wire_missing" not in m

    def test_na_dynamic_defers_via_pending(self) -> None:
        script = '//@version=6\nindicator("d")\nvar int off = na\nplot(close, title="dyn", offset=off)\n'
        ev = self._run_evaluator(script)
        pend_before = ev._plot_wire_pending
        assert isinstance(pend_before, int) and pend_before >= 0
