from __future__ import annotations

from .arrays import ArrayBuiltinsMixin
from .base import BuiltinHandler
from .numeric import NumericBuiltinsMixin
from .strings import StringBuiltinsMixin
from .technical import TechnicalAnalysisMixin


class BuiltinEvaluator(
    NumericBuiltinsMixin,
    StringBuiltinsMixin,
    ArrayBuiltinsMixin,
    TechnicalAnalysisMixin,
):
    """Aggregate the individual builtin dispatch tables."""

    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        dispatch = super()._build_builtin_map()
        dispatch.update(self._numeric_builtin_map())
        dispatch.update(self._string_builtin_map())
        dispatch.update(self._array_builtin_map())
        dispatch.update(self._technical_builtin_map())
        return dispatch
