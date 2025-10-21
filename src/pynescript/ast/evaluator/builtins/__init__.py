from __future__ import annotations

from .arrays import ArrayBuiltinsMixin
from .base import BuiltinHandler
from .input import InputBuiltinsMixin
from .numeric import NumericBuiltinsMixin
from .plotting import PlottingFunctionsMixin
from .request import RequestBuiltinsMixin
from .strings import StringBuiltinsMixin
from .technical import TechnicalAnalysisMixin
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
        return dispatch
