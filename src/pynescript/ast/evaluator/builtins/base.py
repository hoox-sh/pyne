from __future__ import annotations

from collections.abc import Callable
from typing import Any
from typing import NoReturn


BuiltinHandler = Callable[[list[Any]], Any]


class BuiltinDispatchMixin:
    """Shared dispatch utilities for built-in evaluators."""

    _builtin_dispatch: dict[str, BuiltinHandler] | None = None

    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {}

    def _call_builtin(self, name: str, args: list[Any]) -> Any:
        dispatch = self._builtin_dispatch
        if dispatch is None:
            dispatch = self._build_builtin_map()
            self._builtin_dispatch = dispatch
        handler = dispatch.get(name)
        if handler is None:
            msg = f"Unknown built-in function: {name}"
            raise ValueError(msg)
        return handler(args)

    @staticmethod
    def _error(message: str) -> NoReturn:
        raise ValueError(message)
