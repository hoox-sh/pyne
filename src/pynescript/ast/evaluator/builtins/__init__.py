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

"""Pine Script Built-in Functions and Modules.

Implements all Pine Script built-in functions organized by category:

- Numeric: math.*, min, max, round, etc.
- String: str.*, tostring, tonumber, etc.
- Array: array.new, array.push, array.pop, etc.
- Matrix: matrix operations
- Map: map (dictionary) operations
- Technical: ta.* - Technical analysis indicators
- Plotting: plot, plotshape, etc.
- Drawing: line, box, table drawing primitives
- Strategy: strategy.entry, strategy.close, etc.
- Request: request.security for data fetching
- Input: input, input.symbol, etc.
- Utility: type, size, na, etc.
- Color: color.* constants and functions
- Ticker: syminfo, ticker functions
- Timeframe: timeframe.* variables and functions
- Logging: alert, runtime.error

Each category is implemented as a mixin class composed into BuiltinEvaluator.
"""

from __future__ import annotations

from typing import NoReturn

from .alerts import AlertsMixin
from .arrays import ArrayBuiltinsMixin
from .base import BuiltinHandler
from .color import register_color_functions
from .declarations import register_script_declaration_functions
from .drawing import DrawingBuiltinsMixin
from .input import InputBuiltinsMixin
from .logging import register_logging_functions
from .map_evaluator import MapBuiltinsMixin
from .matrix_evaluator import MatrixBuiltinsMixin
from .numeric import NumericBuiltinsMixin
from .plotting import PlottingFunctionsMixin
from .request import FootprintBuiltinsMixin
from .request import RequestBuiltinsMixin
from .strategy import StrategyBuiltinsMixin
from .strategy_constants import StrategyConstantsMixin
from .strings import StringBuiltinsMixin
from .technical import TechnicalAnalysisMixin
from .ticker import register_ticker_functions
from .timeframe import register_timeframe_functions
from .utility import UtilityFunctionsMixin


class BuiltinEvaluator(
    AlertsMixin,
    NumericBuiltinsMixin,
    StringBuiltinsMixin,
    ArrayBuiltinsMixin,
    TechnicalAnalysisMixin,
    PlottingFunctionsMixin,
    UtilityFunctionsMixin,
    InputBuiltinsMixin,
    RequestBuiltinsMixin,
    FootprintBuiltinsMixin,
    DrawingBuiltinsMixin,
    StrategyBuiltinsMixin,
    StrategyConstantsMixin,
    MatrixBuiltinsMixin,
    MapBuiltinsMixin,
):
    """Aggregate the individual builtin dispatch tables."""

    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        dispatch = super()._build_builtin_map()
        dispatch.update(self._alerts_builtin_map())
        dispatch.update(self._numeric_builtin_map())
        dispatch.update(self._string_builtin_map())
        dispatch.update(self._array_builtin_map())
        dispatch.update(self._technical_builtin_map())
        dispatch.update(self._plotting_builtin_map())
        dispatch.update(self._utility_builtin_map())
        dispatch.update(self._input_builtin_map())
        dispatch.update(self._request_builtin_map())
        dispatch.update(self._footprint_builtin_map())
        dispatch.update(self._drawing_builtin_map())
        dispatch.update(self._strategy_builtin_map())
        dispatch.update(self._strategy_constants_builtin_map())
        dispatch.update(self._matrix_builtin_map())
        dispatch.update(self._map_builtin_map())
        # Register Phase 5 functions
        register_ticker_functions(dispatch)
        register_logging_functions(dispatch)
        register_color_functions(dispatch)
        register_timeframe_functions(dispatch)
        register_script_declaration_functions(dispatch)
        # Capture indicator()/strategy()/library() → evaluator._script_declaration
        # so runtimes can expose overlay + title in the API response.
        for _name in ("indicator", "study", "strategy", "library"):
            _raw = dispatch.get(_name)
            if _raw is None:
                continue

            def _decl_handler(
                args: list,
                kwargs: dict | None = None,
                *,
                _raw_fn=_raw,
                _self=self,
                _is_strategy=_name == "strategy",
            ):
                # Script declaration is constant — skip re-build after bar 0
                # (Runtime sets ``_pine_defs_locked`` after the first visit).
                if getattr(_self, "_pine_defs_locked", False):
                    existing = getattr(_self, "_script_declaration", None)
                    if existing is not None:
                        return existing
                decl = _raw_fn(args, kwargs)
                try:
                    _self._script_declaration = decl  # type: ignore[attr-defined]
                except Exception:
                    pass
                if _is_strategy and hasattr(_self, "_apply_strategy_declaration"):
                    try:
                        _self._apply_strategy_declaration(decl)
                    except Exception:
                        pass
                return decl

            dispatch[_name] = _decl_handler
        return dispatch

    @staticmethod
    def _error(message: str) -> NoReturn:
        """Raise a ValueError with the given message.

        Required because BuiltinEvaluator is instantiated directly in tests
        and needs to handle errors without BaseEvaluator's implementation.
        """
        raise ValueError(message)
