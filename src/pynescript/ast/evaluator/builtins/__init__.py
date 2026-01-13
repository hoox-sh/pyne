# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
from .request import RequestBuiltinsMixin
from .strategy import StrategyBuiltinsMixin
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
    DrawingBuiltinsMixin,
    StrategyBuiltinsMixin,
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
        dispatch.update(self._drawing_builtin_map())
        dispatch.update(self._strategy_builtin_map())
        dispatch.update(self._matrix_builtin_map())
        dispatch.update(self._map_builtin_map())
        # Register Phase 5 functions
        register_ticker_functions(dispatch)
        register_logging_functions(dispatch)
        register_color_functions(dispatch)
        register_timeframe_functions(dispatch)
        register_script_declaration_functions(dispatch)
        register_script_declaration_functions(dispatch)
        return dispatch

    def _error(self, msg: str):
        """Raise a ValueError with the given message.
        
        Required because BuiltinEvaluator is instantiated directly in tests
        and needs to handle errors without BaseEvaluator's implementation.
        """
        raise ValueError(msg)
