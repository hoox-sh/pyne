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

"""In-process strategy study: parse-cached Runtime loop + walk-forward."""

from __future__ import annotations

import math
import random
import re
import time
from collections.abc import Callable
from typing import Any

from pynescript.optimize.events_score import build_strategy_stats
from pynescript.optimize.objective import REJECT
from pynescript.optimize.objective import parse_objective
from pynescript.optimize.objective import score_stats
from pynescript.optimize.samplers import make_sampler
from pynescript.optimize.samplers import parse_sampler
from pynescript.optimize.space import SearchSpace
from pynescript.optimize.space import clamp_params
from pynescript.optimize.types import MAX_ENGINE_RUNS
from pynescript.optimize.types import MAX_TRIALS
from pynescript.optimize.types import ObjectiveId
from pynescript.optimize.types import ParamValue
from pynescript.optimize.types import StrategyStats
from pynescript.optimize.types import StudyResult
from pynescript.optimize.types import TrialResult
from pynescript.optimize.types import ValidationSpec
from pynescript.optimize.walk_forward import apply_warmup
from pynescript.optimize.walk_forward import estimated_runs
from pynescript.optimize.walk_forward import holdout_split
from pynescript.optimize.walk_forward import rolling_windows

# Same declaration header as ``runtime.host._SCRIPT_HEADER_RE``.
_SCRIPT_DECL = re.compile(r"(?m)^\s*(indicator|strategy|library|study)\s*\(")


def is_strategy_script(source: str) -> bool:
    """True when the first script declaration is ``strategy(``."""
    m = _SCRIPT_DECL.search(source or "")
    return bool(m and m.group(1) == "strategy")


class StudyCancelled(Exception):
    """Raised when ``should_stop`` returns true mid-study."""


class TooManyRuns(Exception):
    """Raised when another engine run would exceed ``MAX_ENGINE_RUNS``."""


def _mean_stats(rows: list[StrategyStats]) -> StrategyStats | None:
    if not rows:
        return None
    trades = sum(s.trades for s in rows)
    wins = sum(s.wins for s in rows)
    losses = sum(s.losses for s in rows)
    total_pnl = sum(s.total_pnl for s in rows)
    traded = [s for s in rows if s.trades > 0]
    if traded:
        win_rate = sum(s.win_rate for s in traded) / len(traded)
        finite_pf = [s.profit_factor for s in traded if math.isfinite(s.profit_factor)]
        if finite_pf:
            profit_factor = sum(finite_pf) / len(finite_pf)
        elif any(s.profit_factor > 0 and not math.isfinite(s.profit_factor) for s in traded):
            profit_factor = 1.0e6
        else:
            profit_factor = 0.0
    else:
        win_rate = 0.0
        profit_factor = 0.0
    return StrategyStats(
        total_pnl=total_pnl,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_trade=(total_pnl / trades) if trades else 0.0,
        max_dd=max(s.max_dd for s in rows),
        wins=wins,
        losses=losses,
        trades=trades,
    )


def _slice_bars(ohlcv: list[dict[str, Any]], sl: slice) -> list[dict[str, Any]]:
    return ohlcv[sl]


def _bar_open_time(bar: dict[str, Any]) -> float | None:
    raw = bar.get("time", bar.get("bar_time"))
    if raw is None:
        return None
    try:
        t = float(raw)
    except (TypeError, ValueError):
        return None
    return t if t == t else None


def _score_window(bars: list[dict[str, Any]] | None) -> tuple[float, float] | None:
    """``(t0, t1)`` of bar open times, or ``None`` when the slice has no times."""
    if not bars:
        return None
    times = [t for t in (_bar_open_time(b) for b in bars if isinstance(b, dict)) if t is not None]
    if not times:
        return None
    return min(times), max(times)


def _test_run_bars(
    ohlcv: list[dict[str, Any]],
    train_sl: slice,
    test_sl: slice,
    warmup_bars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
    """Test-window run bars plus original test slice when warmup prepends history."""
    test_bars = _slice_bars(ohlcv, test_sl)
    if warmup_bars > 0:
        run_sl = apply_warmup(train_sl, test_sl, warmup_bars)
        return _slice_bars(ohlcv, run_sl), test_bars
    return test_bars, None


def run_once(
    runtime: Any,
    script: str,
    bars: list[dict[str, Any]],
    inputs: dict[str, ParamValue],
    *,
    symbol: str = "CHART",
    libraries: list[dict[str, Any]] | None = None,
    score_bars: list[dict[str, Any]] | None = None,
) -> tuple[StrategyStats | None, str | None]:
    """One interpret ``Runtime.run``; returns (stats, error)."""
    try:
        result = runtime.run(
            script,
            bars,
            mode="interpret",
            inputs=dict(inputs) if inputs else None,
            libraries=libraries or None,
        )
    except Exception as exc:  # noqa: BLE001 — trial isolation
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(result, dict):
        return None, "engine returned a non-object"
    if result.get("error"):
        return None, str(result.get("error"))
    events = result.get("events")
    if not isinstance(events, list):
        events = []
    return build_strategy_stats(events, score_window=_score_window(score_bars)), None


def run_study(
    script: str,
    ohlcv: list[dict[str, Any]],
    space: SearchSpace,
    *,
    n_trials: int = 30,
    sampler: str = "auto",
    objective: str = "composite",
    validation: ValidationSpec | None = None,
    min_trades: int = 5,
    seed: int | None = None,
    symbol: str = "CHART",
    oos_every_trial: bool = True,
    should_stop: Callable[[], bool] | None = None,
    on_trial: Callable[[TrialResult], None] | None = None,
    runtime: Any | None = None,
    libraries: list[dict[str, Any]] | None = None,
    fixed_inputs: dict[str, Any] | None = None,
) -> StudyResult:
    """Run ``n_trials`` interpret evaluations and pick the best OOS (or IS) score.

    Reuses one :class:`~pynescript.runtime.Runtime` instance so the host parse
    cache stays warm. Always interpret — input overrides skip compile.
    """
    t0 = time.perf_counter()
    val = validation or ValidationSpec()
    warning: str | None = None
    if not is_strategy_script(script):
        return StudyResult(
            status="error",
            sampler=sampler,
            objective=objective,
            validation=val,
            n_trials=0,
            error="NOT_A_STRATEGY: hyperparameter search is only for strategy() scripts",
            ms=(time.perf_counter() - t0) * 1000.0,
        )
    if not ohlcv:
        return StudyResult(
            status="error",
            sampler=sampler,
            objective=objective,
            validation=val,
            n_trials=0,
            error="NO_DATA",
            ms=(time.perf_counter() - t0) * 1000.0,
        )
    if not space.params:
        return StudyResult(
            status="error",
            sampler=sampler,
            objective=objective,
            validation=val,
            n_trials=0,
            error="EMPTY_SPACE",
            ms=(time.perf_counter() - t0) * 1000.0,
        )

    n = int(n_trials)
    if n < 1:
        n = 1
    if n > MAX_TRIALS:
        warning = f"n_trials capped at {MAX_TRIALS}"
        n = MAX_TRIALS

    try:
        obj: ObjectiveId = parse_objective(objective)
        sampler_name = parse_sampler(sampler, n_trials=n)
        smp = make_sampler(sampler_name, n_trials=n)
        build = getattr(smp, "build", None)
        if callable(build):
            build(space)
    except ValueError as exc:
        return StudyResult(
            status="error",
            sampler=str(sampler),
            objective=str(objective),
            validation=val,
            n_trials=n,
            error=str(exc),
            warning=warning,
            ms=(time.perf_counter() - t0) * 1000.0,
        )

    if val.mode == "in-sample":
        warning = (
            (warning + "; " if warning else "")
            + "In-sample only overfits. Prefer holdout."
        )

    n_bars = len(ohlcv)
    est = estimated_runs(n, val, n_bars, oos_every_trial=oos_every_trial)
    if est > MAX_ENGINE_RUNS:
        return StudyResult(
            status="error",
            sampler=sampler_name,
            objective=obj,
            validation=val,
            n_trials=n,
            error=f"TOO_MANY_RUNS: estimated {est} engine runs (cap {MAX_ENGINE_RUNS})",
            warning=warning,
            ms=(time.perf_counter() - t0) * 1000.0,
        )

    if runtime is None:
        from pynescript.runtime import Runtime

        runtime = Runtime(symbol=symbol)

    rng = random.Random(seed)
    history: list[TrialResult] = []
    engine_runs = 0
    status = "success"
    study_error: str | None = None
    runs_per_trial = estimated_runs(1, val, n_bars, oos_every_trial=oos_every_trial)

    base_inputs: dict[str, Any] = dict(fixed_inputs or {})

    def eval_window(
        bars: list[dict[str, Any]],
        params: dict[str, ParamValue],
        score_bars: list[dict[str, Any]] | None = None,
    ) -> tuple[StrategyStats | None, str | None]:
        nonlocal engine_runs
        if engine_runs >= MAX_ENGINE_RUNS:
            raise TooManyRuns
        engine_runs += 1
        merged: dict[str, ParamValue] = {**base_inputs, **params}
        return run_once(
            runtime,
            script,
            bars,
            merged,
            symbol=symbol,
            libraries=libraries,
            score_bars=score_bars,
        )

    try:
        for i in range(n):
            if should_stop and should_stop():
                raise StudyCancelled
            if runs_per_trial > 0 and engine_runs + runs_per_trial > MAX_ENGINE_RUNS:
                raise TooManyRuns
            t_trial = time.perf_counter()
            params = clamp_params(space, smp.suggest(space, history, rng))
            is_stats: StrategyStats | None = None
            oos_stats: StrategyStats | None = None
            err: str | None = None
            runs_before = engine_runs

            if val.mode == "in-sample":
                is_stats, err = eval_window(ohlcv, params)
            elif val.mode == "holdout":
                split = holdout_split(n_bars, val)
                if split is None:
                    err = "holdout split needs more bars"
                else:
                    train_sl, test_sl = split
                    is_stats, err = eval_window(_slice_bars(ohlcv, train_sl), params)
                    if err is None and oos_every_trial:
                        run_bars, score_bars = _test_run_bars(
                            ohlcv, train_sl, test_sl, val.warmup_bars
                        )
                        oos_stats, oos_err = eval_window(run_bars, params, score_bars)
                        if oos_err:
                            err = oos_err
            else:
                folds = rolling_windows(n_bars, val)
                if not folds:
                    err = "walk-forward produced no windows (check train/test/step)"
                else:
                    is_rows: list[StrategyStats] = []
                    oos_rows: list[StrategyStats] = []
                    for train_sl, test_sl in folds:
                        if should_stop and should_stop():
                            raise StudyCancelled
                        if engine_runs >= MAX_ENGINE_RUNS:
                            raise TooManyRuns
                        st, e1 = eval_window(_slice_bars(ohlcv, train_sl), params)
                        if e1:
                            err = e1
                            break
                        if st is not None:
                            is_rows.append(st)
                        run_bars, score_bars = _test_run_bars(
                            ohlcv, train_sl, test_sl, val.warmup_bars
                        )
                        ot, e2 = eval_window(run_bars, params, score_bars)
                        if e2:
                            err = e2
                            break
                        if ot is not None:
                            oos_rows.append(ot)
                    if err is None:
                        is_stats = _mean_stats(is_rows)
                        oos_stats = _mean_stats(oos_rows)

            is_score = score_stats(is_stats, obj, min_trades=min_trades) if err is None else None
            oos_score = (
                score_stats(oos_stats, obj, min_trades=min_trades)
                if err is None and oos_stats is not None
                else None
            )
            trial = TrialResult(
                index=i,
                params=params,
                is_stats=is_stats,
                oos_stats=oos_stats,
                is_score=is_score,
                oos_score=oos_score,
                error=err,
                engine_runs=engine_runs - runs_before,
                ms=(time.perf_counter() - t_trial) * 1000.0,
            )
            history.append(trial)
            if on_trial:
                on_trial(trial)
    except StudyCancelled:
        status = "cancelled"
    except TooManyRuns:
        status = "error"
        study_error = f"TOO_MANY_RUNS: {engine_runs} engine runs (cap {MAX_ENGINE_RUNS})"

    best_index: int | None = None
    best_params: dict[str, ParamValue] | None = None
    best_is: float | None = None
    best_oos: float | None = None
    rankable = [t for t in history if t.error is None]
    if rankable:
        def key(t: TrialResult) -> tuple[float, float]:
            oos = t.oos_score if t.oos_score is not None else REJECT
            inn = t.is_score if t.is_score is not None else REJECT
            # Prefer OOS when present; IS is the tie-break.
            return (oos if val.mode != "in-sample" else inn, inn)

        winner = max(rankable, key=key)
        top = key(winner)
        # Holdout/WF require a finite OOS (primary) score; in-sample uses IS.
        if top[0] > REJECT:
            best_index = winner.index
            best_params = dict(winner.params)
            best_is = winner.is_score
            best_oos = winner.oos_score

    return StudyResult(
        status=status,
        sampler=sampler_name,
        objective=obj,
        validation=val,
        n_trials=n,
        trials=history,
        best_index=best_index,
        best_params=best_params,
        best_is_score=best_is,
        best_oos_score=best_oos,
        engine_runs=engine_runs,
        ms=(time.perf_counter() - t0) * 1000.0,
        warning=warning,
        error=study_error,
    )
