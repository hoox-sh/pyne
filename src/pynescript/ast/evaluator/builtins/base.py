# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import inspect

from collections.abc import Callable
from typing import Any
from typing import NoReturn


BuiltinHandler = Callable[[list[Any]], Any]


class BuiltinDispatchMixin:
    """Shared dispatch utilities for built-in evaluators."""

    _builtin_dispatch: dict[str, BuiltinHandler] | None = None

    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {}

    def _call_builtin(self, name: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        dispatch = self._builtin_dispatch
        if dispatch is None:
            dispatch = self._build_builtin_map()
            self._builtin_dispatch = dispatch
        handler = dispatch.get(name)
        if handler is None:
            msg = (
                f"Unknown built-in function: '{name}'. "
                f"Available modules: math, str, array, ta, input, request, line, box, label, table, strategy. "
                f"Use 'ta.<name>' for technical analysis, 'math.<name>' for math functions."
            )
            raise ValueError(msg)
        if kwargs:
            # Some handlers accept (args, kwargs) directly
            # (e.g. _as_builtin_handler which wraps indicator/strategy).
            # Others like _handle_input_int only accept a single args list.
            try:
                return handler(args, kwargs)
            except TypeError:
                pass
            # Fallback: merge kwargs into positional args
            merged = _merge_kwargs_into_args(args, kwargs, handler)
            return handler(merged)
        return handler(args)

    @staticmethod
    def _error(message: str) -> NoReturn:
        raise ValueError(message)


def _merge_kwargs_into_args(
    args: list[Any],
    kwargs: dict[str, Any],
    handler: Callable,
) -> list[Any]:
    """Merge keyword arguments into the positional args list.

    Inspects the handler's signature to map keyword names to positional
    indices. Falls back to checking for a ``_KWARG_ORDER`` attribute on
    the handler (used by ``input.*`` functions whose signature is just
    ``(self, args)`` but whose first positional argument is ``defval``).
    """
    try:
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        start = 1 if params and params[0].name == "self" else 0
        param_names = [p.name for p in params[start:]]
    except (ValueError, TypeError):
        param_names = []

    if not param_names:
        # Check for a _KWARG_ORDER attribute on the handler
        kwarg_order: list[str] | None = getattr(handler, "_KWARG_ORDER", None)
        if kwarg_order:
            merged = list(args)
            for key, val in kwargs.items():
                if key in kwarg_order:
                    idx = kwarg_order.index(key)
                    while len(merged) <= idx:
                        merged.append(None)
                    merged[idx] = val
                else:
                    merged.append(val)
            return merged
        return list(args) + list(kwargs.values())

    merged = list(args)
    for key, val in kwargs.items():
        if key in param_names:
            idx = param_names.index(key)
            while len(merged) <= idx:
                merged.append(None)
            merged[idx] = val
        else:
            merged.append(val)
    return merged
