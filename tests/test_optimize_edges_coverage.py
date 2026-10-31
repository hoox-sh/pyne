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

"""Edge coverage for pynescript.optimize events_score / objective / space."""

from __future__ import annotations

import math

import pytest

from pynescript.optimize.events_score import build_strategy_stats
from pynescript.optimize.objective import REJECT
from pynescript.optimize.objective import parse_objective
from pynescript.optimize.objective import score_stats
from pynescript.optimize.space import clamp_params
from pynescript.optimize.space import clamp_value
from pynescript.optimize.space import grid_size
from pynescript.optimize.space import param_from_mapping
from pynescript.optimize.space import space_from_input_defs
from pynescript.optimize.space import space_from_payload
from pynescript.optimize.types import ParamSpec
from pynescript.optimize.types import SearchSpace
from pynescript.optimize.types import StrategyStats


class TestBuildStrategyStatsEdges:
    def test_non_dict_events_skipped(self) -> None:
        events = [
            "noise",
            42,
            None,
            {
                "kind": "entry",
                "id": "L",
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "L",
                "bar_time": 2,
                "ohlc": [12, 13, 11, 12],
            },
        ]
        stats = build_strategy_stats(events)  # type: ignore[arg-type]
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(2.0)

    def test_cancel_events_ignored(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "cancel", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "cancel_all", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(1.0)

    def test_exit_placement_without_fill_no_trade(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "exit", "id": "XL", "bar_time": 2, "ohlc": [12, 13, 11, 12]},
            {"type": "strategy.exit", "id": "XL", "bar_time": 2, "ohlc": [12, 13, 11, 12]},
        ]
        assert build_strategy_stats(events).trades == 0

    def test_non_fill_order_ignored(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "order", "id": "XL", "comment": "place", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
            {"kind": "close", "id": "L", "bar_time": 3, "ohlc": [12, 13, 11, 12]},
        ]
        assert build_strategy_stats(events).trades == 1

    def test_fill_comment_prefers_limit_then_stop(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {
                "kind": "order",
                "id": "XL",
                "from_entry": "L",
                "comment": "fill:limit",
                "bar_time": 2,
                "limit": 14.0,
                "stop": 8.0,
                "ohlc": [12, 13, 11, 12],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(4.0)

        events2 = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {
                "kind": "order",
                "id": "XL",
                "from_entry": "L",
                "comment": "fill",
                "bar_time": 2,
                "stop": 9.0,
                "ohlc": [12, 13, 11, 12],
            },
        ]
        assert build_strategy_stats(events2).total_pnl == pytest.approx(-1.0)

    def test_ohlc_price_fallback_and_explicit_price(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "price": 10.0},
            {"kind": "close", "id": "L", "bar_time": 2, "ohlc": [1, 2, 0, 13.0]},
        ]
        assert build_strategy_stats(events).total_pnl == pytest.approx(3.0)

    def test_missing_time_or_price_skipped(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "ohlc": [10, 11, 9, 10]},  # no time
            {"kind": "entry", "id": "L", "bar_time": "bad", "ohlc": [10, 11, 9, 10]},
            {"kind": "entry", "id": "L", "bar_time": 1},  # no price/ohlc
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
        ]
        assert build_strategy_stats(events).trades == 1

    def test_score_window_filters_close(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "bar_time": 3, "ohlc": [15, 16, 14, 15]},
        ]
        inside = build_strategy_stats(events, score_window=(2.0, 4.0))
        assert inside.trades == 1
        outside = build_strategy_stats(events, score_window=(10.0, 20.0))
        assert outside.trades == 0

    def test_close_all(self) -> None:
        events = [
            {"kind": "entry", "id": "A", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "entry", "id": "B", "bar_time": 1, "ohlc": [20, 21, 19, 20]},
            {"kind": "close_all", "bar_time": 2, "ohlc": [12, 13, 11, 12]},
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 2
        # A: +2, B: 12-20 = -8
        assert stats.total_pnl == pytest.approx(-6.0)

    def test_closeall_alias(self) -> None:
        events = [
            {"kind": "entry", "id": "A", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "closeall", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
        ]
        assert build_strategy_stats(events).trades == 1

    def test_partial_qty_and_zero_qty_ignored(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "qty": 3, "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "qty": 0, "bar_time": 2, "ohlc": [12, 13, 11, 12]},
            {"kind": "close", "id": "L", "qty": 1, "bar_time": 3, "ohlc": [12, 13, 11, 12]},
            {"kind": "close", "id": "L", "qty": 2, "bar_time": 4, "ohlc": [13, 14, 12, 13]},
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 2
        assert stats.total_pnl == pytest.approx(2.0 + 6.0)

    def test_short_roundtrip(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "S",
                "direction": "short",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "S",
                "direction": "short",
                "qty": 1,
                "bar_time": 2,
                "ohlc": [8, 9, 7, 8],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(2.0)
        assert stats.wins == 1

    def test_kind_short_alias_opens_short(self) -> None:
        events = [
            {"kind": "short", "id": "S", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "closeshort", "id": "S", "bar_time": 2, "ohlc": [9, 10, 8, 9]},
        ]
        assert build_strategy_stats(events).total_pnl == pytest.approx(1.0)

    def test_profit_factor_inf_when_only_wins(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "bar_time": 2, "ohlc": [12, 13, 11, 12]},
        ]
        stats = build_strategy_stats(events)
        assert math.isinf(stats.profit_factor)
        assert stats.profit_factor > 0

    def test_fill_own_id_without_from_entry_is_entry_fill(self) -> None:
        # Opening fill with same id and no from_entry must not close itself.
        events = [
            {
                "kind": "order",
                "id": "L",
                "comment": "fill",
                "qty": 1,
                "bar_time": 1,
                "limit": 10.0,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "order",
                "id": "XL",
                "from_entry": "L",
                "comment": "fill",
                "qty": 1,
                "bar_time": 2,
                "limit": 11.0,
                "ohlc": [11, 12, 10, 11],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(1.0)

    def test_single_open_resolve_by_other_id(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "other", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
        ]
        assert build_strategy_stats(events).trades == 1

    def test_invalid_qty_falls_back(self) -> None:
        events = [
            {"kind": "entry", "id": "L", "qty": "bad", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"kind": "close", "id": "L", "qty": "", "bar_time": 2, "ohlc": [11, 12, 10, 11]},
        ]
        assert build_strategy_stats(events).total_pnl == pytest.approx(1.0)

    def test_event_kind_from_type_or_event_keys(self) -> None:
        events = [
            {"type": "entry", "id": "L", "bar_time": 1, "ohlc": [10, 11, 9, 10]},
            {"event": "close", "id": "L", "bar_time": 2, "ohlc": [12, 13, 11, 12]},
        ]
        assert build_strategy_stats(events).trades == 1


class TestObjectiveEdges:
    def test_score_none_and_min_trades(self) -> None:
        assert score_stats(None) == REJECT
        s = StrategyStats(total_pnl=10, trades=0, max_dd=0.0)
        assert score_stats(s, "net_pnl", min_trades=0) == 10.0
        assert score_stats(s, "net_pnl", min_trades=1) == REJECT

    def test_net_pnl_and_calmar(self) -> None:
        s = StrategyStats(total_pnl=50, trades=5, max_dd=0.0)
        assert score_stats(s, "net_pnl") == 50.0
        # max_dd floor 1e-9
        assert score_stats(s, "calmar") == pytest.approx(50.0 / 1e-9)

    def test_profit_factor_inf_and_neg_inf(self) -> None:
        wins = StrategyStats(total_pnl=5, trades=5, profit_factor=float("inf"))
        assert score_stats(wins, "profit_factor") == 1.0e6
        lost = StrategyStats(total_pnl=-5, trades=5, profit_factor=float("-inf"))
        assert score_stats(lost, "profit_factor") == REJECT

    def test_composite_sign(self) -> None:
        pos = StrategyStats(total_pnl=9, trades=9, max_dd=0.0)
        neg = StrategyStats(total_pnl=-9, trades=9, max_dd=0.0)
        assert score_stats(pos, "composite") > 0
        assert score_stats(neg, "composite") < 0

    def test_parse_objective_aliases(self) -> None:
        assert parse_objective(None) == "composite"
        assert parse_objective("  PnL ") == "net_pnl"
        assert parse_objective("net") == "net_pnl"
        assert parse_objective("profit") == "net_pnl"
        assert parse_objective("pf") == "profit_factor"
        assert parse_objective("profitfactor") == "profit_factor"
        assert parse_objective("dd") == "calmar"
        assert parse_objective("calmar_like") == "calmar"
        assert parse_objective("COMPOSITE") == "composite"

    def test_parse_objective_rejects(self) -> None:
        with pytest.raises(ValueError, match="unknown objective"):
            parse_objective("sharpe")
        with pytest.raises(ValueError, match="unknown objective"):
            parse_objective("nonsense")


class TestSpaceEdges:
    def test_param_from_mapping_name_sources(self) -> None:
        a = param_from_mapping({"title": "Fast", "kind": "int", "min": 1, "max": 3})
        assert a.name == "Fast" and a.kind == "int"
        b = param_from_mapping({"id": "Slow", "type": "float", "minval": 0.1, "maxval": 0.5})
        assert b.name == "Slow" and b.kind == "float"

    def test_param_price_and_categorical_aliases(self) -> None:
        p = param_from_mapping({"name": "Px", "kind": "price", "min": 1, "max": 2})
        assert p.kind == "float"
        c = param_from_mapping({"name": "Side", "kind": "select", "choices": ["A", "B"]})
        assert c.kind == "categorical"
        d = param_from_mapping({"name": "M", "type": "string", "options": ["x"]})
        assert d.kind == "categorical" and d.choices == ("x",)

    def test_param_bool(self) -> None:
        b = param_from_mapping({"name": "On", "kind": "bool"})
        assert b.choices == (False, True)

    def test_param_errors(self) -> None:
        with pytest.raises(ValueError, match="missing name"):
            param_from_mapping({"kind": "int", "min": 1, "max": 2})
        with pytest.raises(ValueError, match="unsupported"):
            param_from_mapping({"name": "X", "kind": "color"})
        with pytest.raises(ValueError, match="choices"):
            param_from_mapping({"name": "E", "kind": "enum"})
        with pytest.raises(ValueError, match="min and max"):
            param_from_mapping({"name": "N", "kind": "int", "min": 1})
        with pytest.raises(ValueError, match="must differ"):
            param_from_mapping({"name": "N", "kind": "int", "min": 2, "max": 2})

    def test_param_swaps_inverted_bounds(self) -> None:
        p = param_from_mapping({"name": "N", "kind": "int", "min": 5, "max": 2})
        assert p.min == 2 and p.max == 5

    def test_space_from_payload_shapes(self) -> None:
        space = space_from_payload([{"name": "A", "kind": "bool"}])
        assert space.names() == ["A"]
        existing = SearchSpace(params=[ParamSpec("Z", "bool", choices=(False, True))])
        assert space_from_payload(existing) is existing
        with pytest.raises(ValueError, match="object with params"):
            space_from_payload("bad")
        with pytest.raises(ValueError, match="no parameters"):
            space_from_payload({"params": []})
        with pytest.raises(ValueError, match="must be an object"):
            space_from_payload({"params": ["x"]})
        with pytest.raises(ValueError, match="duplicate"):
            space_from_payload(
                {
                    "parameters": [
                        {"name": "A", "kind": "bool"},
                        {"name": "A", "kind": "bool"},
                    ]
                }
            )

    def test_space_from_input_defs(self) -> None:
        defs = [
            {"title": "Len", "type": "int", "minval": 2, "maxval": 10},
            {"title": "Src", "type": "source"},
            {"title": "On", "type": "bool"},
            {"id": "", "type": "int", "min": 1, "max": 2},
            "skip-me",
            {"title": "NoBounds", "type": "float"},
            {"title": "Extra", "type": "float", "min": 0, "max": 1},
        ]
        space = space_from_input_defs(defs, include={"Len", "On", "Extra", "NoBounds"})
        assert set(space.names()) == {"Len", "On", "Extra"}

        with_override = space_from_input_defs(
            [{"title": "NoBounds", "type": "float"}],
            overrides={"NoBounds": {"min": 0, "max": 5}},
        )
        assert with_override.names() == ["NoBounds"]

        with pytest.raises(ValueError, match="no searchable"):
            space_from_input_defs([{"title": "Src", "type": "source"}])

    def test_clamp_value_bool_categorical_numeric(self) -> None:
        b = ParamSpec("On", "bool", choices=(False, True))
        assert clamp_value(b, "YES") is True
        assert clamp_value(b, "0") is False
        assert clamp_value(b, 1) is True

        c = ParamSpec("Side", "categorical", choices=("A", "B"))
        assert clamp_value(c, "B") == "B"
        assert clamp_value(c, "nope") == "A"
        empty = ParamSpec("X", "categorical", choices=())
        assert clamp_value(empty, 9) == "9"

        i = ParamSpec("N", "int", min=1, max=5, step=2)
        assert clamp_value(i, 4.6) == 5
        assert clamp_value(i, 99) == 5
        assert clamp_value(i, None) == 1

        f = ParamSpec("F", "float", min=0.0, max=1.0, step=0.25)
        assert clamp_value(f, 0.3) == pytest.approx(0.25)
        assert clamp_value(f, "x") == 0.0

    def test_clamp_params_fills_all(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": "On", "kind": "bool"},
                    {"name": "N", "kind": "int", "min": 1, "max": 3},
                ]
            }
        )
        got = clamp_params(space, {"On": "on"})
        assert got["On"] is True
        assert got["N"] == 1

    def test_grid_size_kinds(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": "On", "kind": "bool"},
                    {"name": "Side", "kind": "categorical", "choices": ["A", "B", "C"]},
                    {"name": "N", "kind": "int", "min": 1, "max": 4},
                    {"name": "F", "kind": "float", "min": 0, "max": 1},
                ]
            }
        )
        # bool*cat*int*float_default = 2 * 3 * 4 * min(8,max_points default path)
        n = grid_size(space, max_points=8)
        assert n == 2 * 3 * 4 * 8

        stepped = space_from_payload({"params": [{"name": "X", "kind": "float", "min": 0, "max": 1, "step": 0.5}]})
        assert grid_size(stepped, max_points=32) == 3

        huge = space_from_payload(
            {"params": [{"name": f"P{i}", "kind": "int", "min": 1, "max": 100} for i in range(6)]}
        )
        assert grid_size(huge, max_points=32) > 10_000_000
