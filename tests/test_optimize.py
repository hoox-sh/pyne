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

"""Strategy hyperparameter search: space, scoring, samplers, study, /optimize."""

from __future__ import annotations

import json
import math
import random

import pytest

from pynescript.optimize.events_score import build_strategy_stats
from pynescript.optimize.objective import REJECT
from pynescript.optimize.objective import score_stats
from pynescript.optimize.samplers import GridSampler
from pynescript.optimize.samplers import RandomSampler
from pynescript.optimize.samplers import TPESampler
from pynescript.optimize.samplers import make_sampler
from pynescript.optimize.samplers import parse_sampler
from pynescript.optimize.space import clamp_params
from pynescript.optimize.space import grid_size
from pynescript.optimize.space import space_from_payload
from pynescript.optimize.study import is_strategy_script
from pynescript.optimize.study import run_study
from pynescript.optimize.types import SearchSpace
from pynescript.optimize.types import StrategyStats
from pynescript.optimize.types import StudyResult
from pynescript.optimize.types import TrialResult
from pynescript.optimize.types import ValidationSpec
from pynescript.optimize.walk_forward import estimated_runs
from pynescript.optimize.walk_forward import holdout_split
from pynescript.optimize.walk_forward import rolling_windows


SMA_STRAT = """
//@version=6
strategy("HPO SMA")
fast = input.int(5, "Fast", minval=2, maxval=12)
slow = input.int(15, "Slow", minval=8, maxval=30)
f = ta.sma(close, fast)
s = ta.sma(close, slow)
if not na(f) and not na(s)
    if f > s
        strategy.entry("L", strategy.long)
    if f < s
        strategy.close("L")
"""

INDICATOR = """
//@version=6
indicator("not a strat")
len = input.int(14, "Len", minval=2, maxval=40)
plot(ta.sma(close, len))
"""


def _bars(n: int, *, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    price = 100.0
    out: list[dict] = []
    for i in range(n):
        # Two-regime walk so period choice actually changes PnL.
        drift = 0.4 if (i // 25) % 2 == 0 else -0.35
        price = max(10.0, price + drift + rng.uniform(-0.6, 0.6))
        out.append(
            {
                "time": 1_700_000_000 + i * 60,
                "open": price,
                "high": price + 0.4,
                "low": price - 0.4,
                "close": price,
                "volume": 10.0,
            }
        )
    return out


def _space() -> SearchSpace:
    return space_from_payload(
        {
            "params": [
                {"name": "Fast", "kind": "int", "min": 3, "max": 8, "step": 1},
                {"name": "Slow", "kind": "int", "min": 10, "max": 20, "step": 2},
            ]
        }
    )


class TestSpace:
    def test_numeric_requires_bounds(self) -> None:
        with pytest.raises(ValueError, match="min and max"):
            space_from_payload({"params": [{"name": "Fast", "kind": "int"}]})

    def test_clamp_int_step(self) -> None:
        space = _space()
        got = clamp_params(space, {"Fast": 4.6, "Slow": 99})
        assert got["Fast"] == 5
        assert got["Slow"] == 20

    def test_bool_and_enum(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": "On", "kind": "bool"},
                    {"name": "Side", "kind": "categorical", "choices": ["A", "B"]},
                ]
            }
        )
        got = clamp_params(space, {"On": "true", "Side": "nope"})
        assert got["On"] is True
        assert got["Side"] == "A"

    def test_grid_size_small(self) -> None:
        assert grid_size(_space()) > 1


class TestEventsScore:
    def test_pairs_long_roundtrip(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 2,
                "ohlc": [12, 13, 11, 12],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(2.0)
        assert stats.wins == 1

    def test_empty(self) -> None:
        assert build_strategy_stats([]).trades == 0
        assert build_strategy_stats(None).trades == 0  # type: ignore[arg-type]

    def test_exit_placement_then_fill_uses_fill_price(self) -> None:
        # Broker schema: no ``price`` / ``from_entry``; fill carries limit/stop.
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "exit",
                "id": "XL",
                "qty": 1,
                "bar_time": 1,
                "limit": 12.5,
                "stop": 8.0,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "order",
                "id": "XL",
                "comment": "fill",
                "qty": 1,
                "bar_time": 3,
                "limit": 12.5,
                "ohlc": [12, 13, 11, 12],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(2.5)
        assert stats.wins == 1

    def test_trail_only_exit_is_placement(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "exit",
                "id": "XT",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "order",
                "id": "XT",
                "comment": "fill",
                "qty": 1,
                "bar_time": 4,
                "stop": 9.0,
                "ohlc": [9, 10, 8, 9],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(-1.0)
        assert stats.losses == 1

    def test_score_window_pairs_warmup_entry(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "L",
                "qty": 1,
                "bar_time": 10,
                "ohlc": [15, 16, 14, 15],
            },
        ]
        dropped = build_strategy_stats(events, score_window=(5.0, 20.0))
        assert dropped.trades == 1
        assert dropped.total_pnl == pytest.approx(5.0)
        warmup_close = build_strategy_stats(events, score_window=(5.0, 8.0))
        assert warmup_close.trades == 0

    def test_partial_close_then_remainder(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 2,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "L",
                "qty": 1,
                "bar_time": 2,
                "ohlc": [12, 13, 11, 12],
            },
            {
                "kind": "close",
                "id": "L",
                "qty": 1,
                "bar_time": 3,
                "ohlc": [15, 16, 14, 15],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 2
        assert stats.total_pnl == pytest.approx(7.0)
        assert stats.wins == 2

    def test_breakeven_not_a_loss(self) -> None:
        events = [
            {
                "kind": "entry",
                "id": "L",
                "direction": "long",
                "qty": 1,
                "bar_time": 1,
                "ohlc": [10, 11, 9, 10],
            },
            {
                "kind": "close",
                "id": "L",
                "qty": 1,
                "bar_time": 2,
                "ohlc": [10, 11, 9, 10],
            },
        ]
        stats = build_strategy_stats(events)
        assert stats.trades == 1
        assert stats.total_pnl == pytest.approx(0.0)
        assert stats.wins == 0
        assert stats.losses == 0

    def test_profit_factor_inf_is_json_safe(self) -> None:
        d = StrategyStats(profit_factor=float("inf")).to_dict()
        assert d["profit_factor"] is None
        assert "inf" not in json.dumps(d).lower()
        json.dumps(d, allow_nan=False)
        tr = TrialResult(
            index=0,
            params={},
            is_score=float("inf"),
            oos_score=float("-inf"),
        ).to_dict()
        assert tr["is_score"] is None
        assert tr["oos_score"] is None
        json.dumps(tr, allow_nan=False)
        study = StudyResult(
            status="success",
            sampler="random",
            objective="composite",
            validation=ValidationSpec(),
            n_trials=1,
            best_is_score=1.0,
            best_oos_score=float("-inf"),
        ).to_dict()
        assert study["best_oos_score"] is None
        json.dumps(study, allow_nan=False)


class TestObjective:
    def test_min_trades_rejects(self) -> None:
        s = StrategyStats(total_pnl=100, trades=2, max_dd=0.1)
        assert score_stats(s, "net_pnl", min_trades=5) == REJECT

    def test_composite_ranks_better_pnl(self) -> None:
        a = StrategyStats(total_pnl=10, trades=8, max_dd=0.1)
        b = StrategyStats(total_pnl=2, trades=8, max_dd=0.1)
        assert score_stats(a, "composite") > score_stats(b, "composite")

    def test_profit_factor_inf(self) -> None:
        s = StrategyStats(total_pnl=5, trades=5, profit_factor=float("inf"), wins=5)
        assert math.isfinite(score_stats(s, "profit_factor")) or score_stats(
            s, "profit_factor"
        ) > 0


class TestWalkForward:
    def test_holdout_no_overlap(self) -> None:
        split = holdout_split(100, ValidationSpec(holdout_frac=0.3))
        assert split is not None
        train, test = split
        assert train.stop == test.start
        assert test.stop == 100
        assert train.stop == 70

    def test_rolling_windows(self) -> None:
        folds = rolling_windows(200, ValidationSpec(train_bars=80, test_bars=20, step_bars=20))
        assert folds
        for tr, te in folds:
            assert tr.stop == te.start
            assert te.stop - te.start == 20

    def test_estimated_holdout_doubles(self) -> None:
        spec = ValidationSpec(mode="holdout")
        assert estimated_runs(10, spec, 100, oos_every_trial=True) == 20

    def test_estimated_walk_forward_counts_train_and_test(self) -> None:
        spec = ValidationSpec(mode="walk-forward", train_bars=80, test_bars=20, step_bars=20)
        folds = len(rolling_windows(200, spec))
        assert folds >= 1
        assert estimated_runs(5, spec, 200) == 5 * folds * 2
        empty = ValidationSpec(mode="walk-forward", train_bars=200, test_bars=50)
        assert estimated_runs(10, empty, 120) == 0


class TestSamplers:
    def test_random_in_bounds(self) -> None:
        space = _space()
        rng = random.Random(0)
        smp = RandomSampler()
        for _ in range(20):
            p = smp.suggest(space, [], rng)
            assert 3 <= int(p["Fast"]) <= 8
            assert 10 <= int(p["Slow"]) <= 20

    def test_grid_enumerates(self) -> None:
        space = space_from_payload(
            {"params": [{"name": "N", "kind": "int", "min": 1, "max": 3, "step": 1}]}
        )
        smp = GridSampler(max_cells=10)
        pts = smp.build(space)
        assert {p["N"] for p in pts} == {1, 2, 3}

    def test_grid_refuses_huge(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": "A", "kind": "int", "min": 1, "max": 40},
                    {"name": "B", "kind": "int", "min": 1, "max": 40},
                ]
            }
        )
        with pytest.raises(ValueError, match="grid has"):
            GridSampler(max_cells=10).build(space)

    def test_grid_stepped_float_is_capped_not_refused(self) -> None:
        space = space_from_payload(
            {"params": [{"name": "X", "kind": "float", "min": 0, "max": 1, "step": 0.01}]}
        )
        pts = GridSampler(max_cells=5).build(space)
        assert 1 <= len(pts) <= 16
        assert pts[0]["X"] == 0
        assert pts[-1]["X"] == 1

    def test_grid_refuses_multi_float_product(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": f"X{i}", "kind": "float", "min": 0, "max": 1}
                    for i in range(3)
                ]
            }
        )
        with pytest.raises(ValueError, match="grid has"):
            GridSampler(max_cells=10).build(space)

    def test_random_unstepped_float_is_continuous(self) -> None:
        space = space_from_payload(
            {"params": [{"name": "X", "kind": "float", "min": 0, "max": 1}]}
        )
        rng = random.Random(0)
        smp = RandomSampler()
        vals = [float(smp.suggest(space, [], rng)["X"]) for _ in range(40)]
        assert min(vals) >= 0.0
        assert max(vals) <= 1.0
        assert len({round(v, 6) for v in vals}) > 8

    def test_tpe_suggests_after_seeds(self) -> None:
        space = _space()
        rng = random.Random(1)
        smp = TPESampler(n_startup=4, n_ei_candidates=8)
        hist: list[TrialResult] = []
        for i in range(8):
            params = smp.suggest(space, hist, rng)
            hist.append(
                TrialResult(
                    index=i,
                    params=params,
                    is_score=float(params["Fast"]) - float(params["Slow"]),
                )
            )
        nxt = smp.suggest(space, hist, rng)
        assert "Fast" in nxt and "Slow" in nxt

    def test_auto_sampler(self) -> None:
        assert parse_sampler("auto", n_trials=10) == "random"
        assert parse_sampler("auto", n_trials=30) == "tpe"
        assert make_sampler("random", n_trials=5).name == "random"


class TestStudy:
    def test_rejects_indicator(self) -> None:
        assert not is_strategy_script(INDICATOR)
        out = run_study(INDICATOR, _bars(40), _space(), n_trials=3)
        assert out.status == "error"
        assert out.error and "NOT_A_STRATEGY" in out.error

    def test_strategy_decl_ignores_comment_and_string(self) -> None:
        src = '//@version=6\nindicator("x")\n// strategy("nope")\nplot(close, title="strategy()")\n'
        assert not is_strategy_script(src)
        mixed = '//@version=6\nstrategy("s")\n// leftover\n'
        assert is_strategy_script(mixed)

    def test_in_sample_random_runs(self) -> None:
        out = run_study(
            SMA_STRAT,
            _bars(80),
            _space(),
            n_trials=4,
            sampler="random",
            objective="net_pnl",
            validation=ValidationSpec(mode="in-sample"),
            min_trades=0,
            seed=2,
        )
        assert out.status == "success"
        assert len(out.trials) == 4
        assert out.engine_runs == 4
        assert out.best_params is not None
        assert "Fast" in out.best_params

    def test_holdout_two_runs_per_trial(self) -> None:
        out = run_study(
            SMA_STRAT,
            _bars(80),
            _space(),
            n_trials=2,
            sampler="random",
            objective="composite",
            validation=ValidationSpec(mode="holdout", holdout_frac=0.3),
            min_trades=0,
            seed=3,
        )
        assert out.status == "success"
        assert out.engine_runs == 4
        assert out.trials[0].oos_stats is not None

    def test_grid_too_large_is_error_not_raise(self) -> None:
        space = space_from_payload(
            {
                "params": [
                    {"name": "A", "kind": "int", "min": 1, "max": 40},
                    {"name": "B", "kind": "int", "min": 1, "max": 40},
                ]
            }
        )
        out = run_study(
            SMA_STRAT,
            _bars(40),
            space,
            n_trials=5,
            sampler="grid",
            validation=ValidationSpec(mode="in-sample"),
            min_trades=0,
        )
        assert out.status == "error"
        assert out.error and "grid has" in out.error

    def test_fixed_inputs_merged_under_trial(self) -> None:
        seen: list[dict] = []

        class _Fake:
            def run(self, _script, _bars, **kwargs):
                seen.append(dict(kwargs.get("inputs") or {}))
                return {"events": []}

        space = space_from_payload(
            {"params": [{"name": "Fast", "kind": "int", "min": 3, "max": 4}]}
        )
        run_study(
            SMA_STRAT,
            _bars(20),
            space,
            n_trials=1,
            sampler="random",
            validation=ValidationSpec(mode="in-sample"),
            min_trades=0,
            seed=1,
            runtime=_Fake(),
            fixed_inputs={"Source": "hlc3", "Fast": 99},
        )
        assert seen
        assert seen[0]["Source"] == "hlc3"
        # Trial value wins over the fixed bag for searched names.
        assert seen[0]["Fast"] != 99

    def test_cancel(self) -> None:
        n = {"i": 0}

        def stop() -> bool:
            n["i"] += 1
            return n["i"] > 2

        out = run_study(
            SMA_STRAT,
            _bars(60),
            _space(),
            n_trials=8,
            sampler="random",
            validation=ValidationSpec(mode="in-sample"),
            min_trades=0,
            should_stop=stop,
            seed=4,
        )
        assert out.status == "cancelled"
        assert len(out.trials) < 8
