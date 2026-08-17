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

"""Strategy hyperparameter search (TPE / random / grid + walk-forward).

This package is the evaluation SoT for AXIS Hyperparameter Optimisation.
It loops :class:`~pynescript.runtime.Runtime` with ``input.*`` overrides —
it is not a Pine language surface and does not use ``/backtest/quick``.
"""

from __future__ import annotations

from pynescript.optimize.events_score import build_strategy_stats
from pynescript.optimize.objective import score_stats
from pynescript.optimize.space import SearchSpace
from pynescript.optimize.space import space_from_input_defs
from pynescript.optimize.space import space_from_payload
from pynescript.optimize.study import is_strategy_script
from pynescript.optimize.study import run_study
from pynescript.optimize.types import MAX_TRIALS
from pynescript.optimize.types import ParamSpec
from pynescript.optimize.types import StrategyStats
from pynescript.optimize.types import StudyResult
from pynescript.optimize.types import TrialResult
from pynescript.optimize.types import ValidationSpec

__all__ = [
    "MAX_TRIALS",
    "ParamSpec",
    "SearchSpace",
    "StrategyStats",
    "StudyResult",
    "TrialResult",
    "ValidationSpec",
    "build_strategy_stats",
    "is_strategy_script",
    "run_study",
    "score_stats",
    "space_from_input_defs",
    "space_from_payload",
]
