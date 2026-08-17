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
# MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bar-window splits for holdout and rolling walk-forward."""

from __future__ import annotations

from pynescript.optimize.types import ValidationSpec


def holdout_split(n_bars: int, spec: ValidationSpec) -> tuple[slice, slice] | None:
    """Return ``(train, test)`` slices, or ``None`` if the series is too short."""
    if n_bars < 4:
        return None
    frac = spec.holdout_frac
    if not (0.05 <= frac <= 0.8):
        frac = 0.3
    test_n = max(1, int(round(n_bars * frac)))
    split = n_bars - test_n
    if split < 2:
        return None
    return slice(0, split), slice(split, n_bars)


def rolling_windows(n_bars: int, spec: ValidationSpec) -> list[tuple[slice, slice]]:
    """Anchored-from-start rolling train/test windows.

    Train is ``[0, train_end)`` growing by ``step``; test is the next
    ``test_bars`` after that. Does not overlap train and test.
    """
    train = max(2, int(spec.train_bars))
    test = max(1, int(spec.test_bars))
    step = max(1, int(spec.step_bars))
    out: list[tuple[slice, slice]] = []
    start = train
    while start + test <= n_bars:
        out.append((slice(0, start), slice(start, start + test)))
        start += step
    return out


def apply_warmup(train: slice, test: slice, warmup: int) -> slice:
    """Widen the test slice backward by ``warmup`` bars for lookback fill.

    Scoring still uses only the original test window; the extra prefix is
    so ``ta.*`` has history. The study loop slices bars with this window
    and the caller must still score only test-period trades when using
    warmup — v1 scores the full test-slice run (warmup is applied by
    starting test earlier, which *does* leak a few lookback bars into
    the test *input*. We instead prepend warmup from *train* onto the
    test *run bars* and accept that the first ``warmup`` bars of the
    test eval exist only for state. Trades during the warmup prefix
    should be ignored by the caller. For v1 we keep warmup default 0.
    """
    if warmup <= 0:
        return test
    start = max(train.start or 0, (test.start or 0) - warmup)
    return slice(start, test.stop)


def estimated_runs(
    n_trials: int,
    spec: ValidationSpec,
    n_bars: int,
    *,
    oos_every_trial: bool = True,
) -> int:
    """Engine ``run`` count for a study (used to cap / warn)."""
    if spec.mode == "in-sample":
        return n_trials
    if spec.mode == "holdout":
        return n_trials * (2 if oos_every_trial else 1)
    folds = len(rolling_windows(n_bars, spec))
    if folds < 1:
        return n_trials
    return n_trials * folds
