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

"""Types for strategy hyperparameter search."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal


def _finite_or_none(value: Any) -> Any:
    """Replace non-finite floats so Flask/json can emit strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


ParamValue = int | float | bool | str

SamplerId = Literal["auto", "random", "tpe", "grid"]
ObjectiveId = Literal["net_pnl", "profit_factor", "calmar", "composite"]
ValidationId = Literal["holdout", "walk-forward", "in-sample"]
ParamKind = Literal["int", "float", "bool", "categorical"]

MAX_TRIALS = 200
MAX_ENGINE_RUNS = 400


@dataclass(frozen=True)
class ParamSpec:
    """One searchable Pine ``input.*`` (or strategy-prop) dimension."""

    name: str
    kind: ParamKind
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: tuple[ParamValue, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy."""
        d: dict[str, Any] = {"name": self.name, "kind": self.kind}
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        if self.step is not None:
            d["step"] = self.step
        if self.choices is not None:
            d["choices"] = list(self.choices)
        return d


@dataclass
class SearchSpace:
    """Ordered list of searchable parameters."""

    params: list[ParamSpec] = field(default_factory=list)

    def names(self) -> list[str]:
        """Parameter names in declaration order."""
        return [p.name for p in self.params]

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy."""
        return {"params": [p.to_dict() for p in self.params]}


@dataclass(frozen=True)
class StrategyStats:
    """Closed-trade aggregate used as the HPO objective input."""

    total_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade: float = 0.0
    max_dd: float = 0.0
    wins: int = 0
    losses: int = 0
    trades: int = 0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy (non-finite floats → ``None``)."""
        return {k: _finite_or_none(v) for k, v in asdict(self).items()}


@dataclass
class TrialResult:
    """One evaluated parameter set."""

    index: int
    params: dict[str, ParamValue]
    is_stats: StrategyStats | None = None
    oos_stats: StrategyStats | None = None
    is_score: float | None = None
    oos_score: float | None = None
    error: str | None = None
    engine_runs: int = 0
    ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy (no event arrays)."""
        return {
            "index": self.index,
            "params": dict(self.params),
            "is_stats": self.is_stats.to_dict() if self.is_stats else None,
            "oos_stats": self.oos_stats.to_dict() if self.oos_stats else None,
            "is_score": _finite_or_none(self.is_score),
            "oos_score": _finite_or_none(self.oos_score),
            "error": self.error,
            "engine_runs": self.engine_runs,
            "ms": self.ms,
        }


@dataclass
class ValidationSpec:
    """How bars are split for in-sample vs out-of-sample scoring."""

    mode: ValidationId = "holdout"
    holdout_frac: float = 0.3
    train_bars: int = 200
    test_bars: int = 50
    step_bars: int = 50
    warmup_bars: int = 0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy."""
        return asdict(self)


@dataclass
class StudyResult:
    """Finished (or cancelled) optimisation study."""

    status: str
    sampler: str
    objective: str
    validation: ValidationSpec
    n_trials: int
    trials: list[TrialResult] = field(default_factory=list)
    best_index: int | None = None
    best_params: dict[str, ParamValue] | None = None
    best_is_score: float | None = None
    best_oos_score: float | None = None
    engine_runs: int = 0
    ms: float = 0.0
    warning: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe study payload for ``POST /optimize``."""
        return {
            "status": self.status,
            "sampler": self.sampler,
            "objective": self.objective,
            "validation": self.validation.to_dict(),
            "n_trials": self.n_trials,
            "trials": [t.to_dict() for t in self.trials],
            "best_index": self.best_index,
            "best_params": dict(self.best_params) if self.best_params else None,
            "best_is_score": self.best_is_score,
            "best_oos_score": self.best_oos_score,
            "engine_runs": self.engine_runs,
            "ms": self.ms,
            "warning": self.warning,
            "error": self.error,
        }
