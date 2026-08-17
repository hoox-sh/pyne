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

"""Random, grid, and Tree-structured Parzen Estimator samplers."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any

from pynescript.optimize.space import _axis_cardinality
from pynescript.optimize.space import clamp_value
from pynescript.optimize.types import ParamSpec
from pynescript.optimize.types import ParamValue
from pynescript.optimize.types import SearchSpace
from pynescript.optimize.types import TrialResult


class BaseSampler:
    """Suggest the next parameter assignment."""

    name = "base"

    def suggest(
        self,
        space: SearchSpace,
        history: Sequence[TrialResult],
        rng: random.Random,
    ) -> dict[str, ParamValue]:
        """Return a clamped assignment."""
        raise NotImplementedError


def _sample_axis(spec: ParamSpec, rng: random.Random) -> ParamValue:
    if spec.kind == "bool":
        return bool(rng.randrange(2))
    if spec.kind == "categorical":
        choices = spec.choices or (0,)
        return choices[rng.randrange(len(choices))]
    lo = spec.min if spec.min is not None else 0.0
    hi = spec.max if spec.max is not None else lo + 1.0
    if spec.kind == "int" and (not spec.step or spec.step == 1):
        return int(rng.randint(int(round(lo)), int(round(hi))))
    grid = _axis_grid(spec)
    if grid:
        return grid[rng.randrange(len(grid))]
    return rng.uniform(float(lo), float(hi))


class RandomSampler(BaseSampler):
    """Independent uniform sample per axis."""

    name = "random"

    def suggest(
        self,
        space: SearchSpace,
        history: Sequence[TrialResult],
        rng: random.Random,
    ) -> dict[str, ParamValue]:
        return {spec.name: _sample_axis(spec, rng) for spec in space.params}


def _axis_grid(spec: ParamSpec, max_points: int = 16) -> list[ParamValue]:
    if spec.kind == "bool":
        return [False, True]
    if spec.kind == "categorical":
        return list(spec.choices or ())
    lo = spec.min if spec.min is not None else 0.0
    hi = spec.max if spec.max is not None else lo
    n = _axis_cardinality(spec, max_points=max_points)
    n = max(1, min(n, max_points))
    if n == 1:
        return [clamp_value(spec, lo)]
    vals: list[ParamValue] = []
    for i in range(n):
        t = i / (n - 1)
        vals.append(clamp_value(spec, lo + t * (hi - lo)))
    # unique while preserving order
    seen: set[Any] = set()
    out: list[ParamValue] = []
    for v in vals:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out or [clamp_value(spec, lo)]


def _uncapped_discrete_len(spec: ParamSpec) -> int | None:
    """Uncapped size of a discrete axis, or None if interpolated/capped."""
    if spec.kind == "bool":
        return 2
    if spec.kind == "categorical":
        return max(1, len(spec.choices or ()))
    if spec.kind == "int" and (not spec.step or spec.step == 1):
        lo = spec.min if spec.min is not None else 0.0
        hi = spec.max if spec.max is not None else lo
        return max(1, int(round(hi)) - int(round(lo)) + 1)
    return None


def _emitted_grid_size(axes: list[list[ParamValue]]) -> int:
    size = 1
    for vals in axes:
        if not vals:
            return 0
        size *= len(vals)
    return size


def _has_wide_discrete(space: SearchSpace) -> bool:
    """True when an int/categorical axis is wider than the 16-pt grid cap."""
    for spec in space.params:
        n = _uncapped_discrete_len(spec)
        if n is not None and n > 16:
            return True
    return False


class GridSampler(BaseSampler):
    """Cartesian product of ``_axis_grid`` axes (at most 16 pts per numeric axis)."""

    name = "grid"

    def __init__(self, max_cells: int = 200) -> None:
        self.max_cells = max_cells
        self._points: list[dict[str, ParamValue]] | None = None

    def build(self, space: SearchSpace) -> list[dict[str, ParamValue]]:
        """Materialize the grid (cached)."""
        if self._points is not None:
            return self._points
        axes = [_axis_grid(spec) for spec in space.params]
        size = _emitted_grid_size(axes)
        if size < 1 or (size > self.max_cells and _has_wide_discrete(space)):
            raise ValueError(
                f"grid has {size} cells (cap {self.max_cells}); use random or TPE"
            )
        points: list[dict[str, ParamValue]] = [{}]
        for spec, vals in zip(space.params, axes, strict=True):
            nxt: list[dict[str, ParamValue]] = []
            for base in points:
                for v in vals:
                    row = dict(base)
                    row[spec.name] = v
                    nxt.append(row)
            points = nxt
        self._points = points
        return points

    def suggest(
        self,
        space: SearchSpace,
        history: Sequence[TrialResult],
        rng: random.Random,
    ) -> dict[str, ParamValue]:
        pts = self.build(space)
        used = {tuple(sorted(t.params.items())) for t in history}
        for p in pts:
            key = tuple(sorted(p.items()))
            if key not in used:
                return dict(p)
        return dict(pts[rng.randrange(len(pts))])


def _finished(history: Sequence[TrialResult]) -> list[TrialResult]:
    return [t for t in history if t.error is None and t.is_score is not None]


class TPESampler(BaseSampler):
    """Tree-structured Parzen Estimator (Bergstra et al.).

    After ``n_startup`` random trials, split completed scores at quantile
    ``gamma`` into good/bad. Continuous axes use a 1-D Gaussian KDE;
    categorical/bool use smoothed counts. Candidates are drawn from the
    good density and ranked by ``l(x) / g(x)``.
    """

    name = "tpe"

    def __init__(
        self,
        *,
        gamma: float = 0.25,
        n_startup: int = 10,
        n_ei_candidates: int = 24,
    ) -> None:
        self.gamma = gamma
        self.n_startup = n_startup
        self.n_ei_candidates = n_ei_candidates
        self._random = RandomSampler()

    def suggest(
        self,
        space: SearchSpace,
        history: Sequence[TrialResult],
        rng: random.Random,
    ) -> dict[str, ParamValue]:
        done = _finished(history)
        if len(done) < max(2, self.n_startup):
            return self._random.suggest(space, history, rng)
        ranked = sorted(done, key=lambda t: float(t.is_score), reverse=True)
        n_good = max(1, int(math.ceil(self.gamma * len(ranked))))
        good = ranked[:n_good]
        bad = ranked[n_good:] or ranked[-1:]
        best: dict[str, ParamValue] | None = None
        best_ei = float("-inf")
        for _ in range(self.n_ei_candidates):
            cand = self._sample_good(space, good, rng)
            ei = self._ei(space, cand, good, bad)
            if ei > best_ei:
                best_ei = ei
                best = cand
        return best if best is not None else self._random.suggest(space, history, rng)

    def _sample_good(
        self,
        space: SearchSpace,
        good: Sequence[TrialResult],
        rng: random.Random,
    ) -> dict[str, ParamValue]:
        out: dict[str, ParamValue] = {}
        for spec in space.params:
            vals = [t.params.get(spec.name) for t in good]
            if spec.kind in {"bool", "categorical"}:
                choices = list(spec.choices or (False, True))
                weights = [1.0] * len(choices)
                for v in vals:
                    if v in choices:
                        weights[choices.index(v)] += 1.0  # type: ignore[arg-type]
                out[spec.name] = rng.choices(choices, weights=weights, k=1)[0]
                continue
            numeric = [float(v) for v in vals if isinstance(v, (int, float))]
            if not numeric:
                out[spec.name] = _sample_axis(spec, rng)
                continue
            center = numeric[rng.randrange(len(numeric))]
            sigma = _axis_sigma(spec, numeric)
            raw = rng.gauss(center, sigma)
            out[spec.name] = clamp_value(spec, raw)
        return out

    def _ei(
        self,
        space: SearchSpace,
        cand: dict[str, ParamValue],
        good: Sequence[TrialResult],
        bad: Sequence[TrialResult],
    ) -> float:
        log_l = 0.0
        log_g = 0.0
        for spec in space.params:
            x = cand.get(spec.name)
            gv = [t.params.get(spec.name) for t in good]
            bv = [t.params.get(spec.name) for t in bad]
            log_l += math.log(_density(spec, x, gv) + 1e-12)
            log_g += math.log(_density(spec, x, bv) + 1e-12)
        return log_l - log_g


def _axis_sigma(spec: ParamSpec, numeric: list[float]) -> float:
    lo = spec.min if spec.min is not None else min(numeric)
    hi = spec.max if spec.max is not None else max(numeric)
    span = max(hi - lo, 1e-9)
    if len(numeric) < 2:
        return span / 6.0
    mean = sum(numeric) / len(numeric)
    var = sum((v - mean) ** 2 for v in numeric) / len(numeric)
    return max(math.sqrt(var), span / 8.0, 1e-9)


def _density(spec: ParamSpec, x: ParamValue | None, samples: list[ParamValue | None]) -> float:
    if spec.kind in {"bool", "categorical"}:
        choices = list(spec.choices or (False, True))
        k = max(1, len(choices))
        hits = sum(1 for s in samples if s == x)
        return (hits + 1.0) / (len(samples) + k)
    if not isinstance(x, (int, float)):
        return 1e-12
    numeric = [float(s) for s in samples if isinstance(s, (int, float))]
    if not numeric:
        return 1e-12
    sigma = _axis_sigma(spec, numeric)
    acc = 0.0
    inv = 1.0 / (sigma * math.sqrt(2.0 * math.pi))
    for v in numeric:
        z = (float(x) - v) / sigma
        acc += inv * math.exp(-0.5 * z * z)
    return acc / len(numeric)


def parse_sampler(raw: str | None, *, n_trials: int) -> str:
    """Resolve ``auto`` → random when ``n_trials < 20``, else TPE."""
    s = (raw or "auto").strip().lower()
    if s == "auto":
        return "random" if n_trials < 20 else "tpe"
    if s not in {"random", "tpe", "grid"}:
        raise ValueError(f"unknown sampler: {raw!r}")
    return s


def make_sampler(name: str, *, n_trials: int) -> BaseSampler:
    """Construct a sampler by resolved name."""
    if name == "tpe":
        startup = max(3, min(10, n_trials // 3))
        return TPESampler(n_startup=startup)
    if name == "grid":
        return GridSampler(max_cells=max(n_trials, 1))
    return RandomSampler()
