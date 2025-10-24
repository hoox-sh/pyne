from __future__ import annotations

from .arrays import ArrayBuiltinsMixin
from .base import BuiltinHandler
from .color import register_color_functions
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
        return dispatch
