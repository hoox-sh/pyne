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
