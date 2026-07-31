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

from __future__ import annotations

import inspect
import math

from collections.abc import Callable
from typing import Any
from typing import NoReturn


BuiltinHandler = Callable[[list[Any]], Any]


def pine_expect_int(value: Any, message: str, error: Callable[[str], NoReturn]) -> int:
    """Coerce a Pine value to ``int`` (periods, offsets, indices).

    Hot path: plain ``int`` (not ``bool``) returns immediately — TA periods and
    plot offsets hit this every bar. Unwraps series wrappers, input dicts, and
    list last-samples; floors fractional floats (TV length semantics).

    Raises via *error* with ``Got: <type|na|…>`` so type bugs surface clearly
    instead of a bare message (or silent wrong path).
    """
    # Fast path: true int (bool is an int subclass — reject here)
    if type(value) is int:
        return value

    # Input.* default dict
    if type(value) is dict and "default" in value:
        value = value["default"]
        if type(value) is int:
            return value

    # PineSeries / _SeriesResult / _NaValue
    if not isinstance(value, (list, tuple, str, bytes)) and hasattr(value, "current"):
        if type(value).__name__ == "_NaValue":
            error(f"{message}. Got: na")
        value = value.current
        if type(value) is int:
            return value

    # Series of periods → current (last) bar
    if type(value) is list:
        if not value:
            error(f"{message}. Got: empty series")
        value = value[-1]
        if type(value) is int:
            return value

    if value is None:
        error(f"{message}. Got: na")

    if type(value) is float:
        if value != value:  # NaN
            error(f"{message}. Got: na")
        return int(math.floor(value))

    if type(value) is bool:
        return int(value)

    if type(value) is str:
        try:
            return int(float(value))
        except ValueError:
            error(f"{message}. Got: str {value!r}")

    error(f"{message}. Got: {type(value).__name__}")
    raise AssertionError("unreachable")  # error() is NoReturn; keep type-checkers happy

# TradingView keyword parameter names for list-style ``ta.*`` handlers.
# Used when the Python handler is ``(self, args)`` and has no real param names.
# Keys are bare names (``ema``) — strip a leading ``ta.`` before lookup.
_TA_KWARG_ORDERS: dict[str, list[str]] = {
    # (source, length)
    "sma": ["source", "length"],
    "ema": ["source", "length"],
    "wma": ["source", "length"],
    "rma": ["source", "length"],
    "hma": ["source", "length"],
    "vwma": ["source", "length"],
    "rsi": ["source", "length"],
    "stdev": ["source", "length"],
    "change": ["source", "length"],
    "mom": ["source", "length"],
    "roc": ["source", "length"],
    "dev": ["source", "length"],
    "variance": ["source", "length"],
    "median": ["source", "length"],
    "mode": ["source", "length"],
    "percentrank": ["source", "length"],
    "highest": ["source", "length"],
    "lowest": ["source", "length"],
    "highestbars": ["source", "length"],
    "lowestbars": ["source", "length"],
    "falling": ["source", "length"],
    "rising": ["source", "length"],
    "range": ["source", "length"],
    "max": ["source", "length"],
    "min": ["source", "length"],
    "sum": ["source", "length"],
    "cum": ["source"],
    "swma": ["source"],
    "vwap": ["source"],
    "cmo": ["source", "length"],
    "cog": ["source", "length"],
    "mfi": ["source", "length"],
    "cci": ["source", "length"],
    "wpr": ["length"],
    "atr": ["length"],
    "tr": ["handle_na"],
    # multi-arg
    "bb": ["source", "length", "mult"],
    "bbw": ["source", "length", "mult"],
    "kc": ["source", "length", "mult"],
    "kcw": ["source", "length", "mult"],
    "alma": ["source", "length", "offset", "sigma"],
    "stoch": ["source", "high", "low", "length"],
    "macd": ["source", "fastlen", "slowlen", "siglen"],
    "tsi": ["source", "short_length", "long_length"],
    "dmi": ["diLength", "adxSmoothing"],
    "supertrend": ["factor", "atrPeriod"],
    "linreg": ["source", "length", "offset"],
    "sar": ["start", "inc", "max"],
    "pivothigh": ["source", "leftbars", "rightbars"],
    "pivotlow": ["source", "leftbars", "rightbars"],
    "valuewhen": ["condition", "source", "occurrence"],
    "crossover": ["source1", "source2"],
    "crossunder": ["source1", "source2"],
    "cross": ["source1", "source2"],
    "correlation": ["source1", "source2", "length"],
    "obv": ["source", "volume"],
    "cmf": ["length"],
    "iii": [],
    "wad": [],
    "wvad": ["length"],
    "nvi": [],
    "pvi": [],
    "accdist": [],
}

# Normalize alternate Pine kw names → canonical names used in _TA_KWARG_ORDERS.
_TA_KWARG_ALIASES: dict[str, str] = {
    "src": "source",
    "series": "source",
    "close": "source",  # some scripts use close= for source slot
    "len": "length",
    "period": "length",
    "length": "length",
    "multiplier": "mult",
    "mult": "mult",
    "std": "mult",
    "stdev": "mult",
    "dev": "mult",
    "fastLength": "fastlen",
    "fast_length": "fastlen",
    "fastlen": "fastlen",
    "slowLength": "slowlen",
    "slow_length": "slowlen",
    "slowlen": "slowlen",
    "signalLength": "siglen",
    "signal_length": "siglen",
    "siglen": "siglen",
    "signal": "siglen",
    "shortlen": "short_length",
    "shortLength": "short_length",
    "short_length": "short_length",
    "longlen": "long_length",
    "longLength": "long_length",
    "long_length": "long_length",
    "leftBars": "leftbars",
    "leftbars": "leftbars",
    "rightBars": "rightbars",
    "rightbars": "rightbars",
    "atr_period": "atrPeriod",
    "atrPeriod": "atrPeriod",
    "factor": "factor",
    "source1": "source1",
    "source2": "source2",
    "series1": "source1",
    "series2": "source2",
    "occurrence": "occurrence",
    "offset": "offset",
    "sigma": "sigma",
    "start": "start",
    "inc": "inc",
    "increment": "inc",
    "maximum": "max",
    "max": "max",
    "diLength": "diLength",
    "adxSmoothing": "adxSmoothing",
    "handle_na": "handle_na",
    "volume": "volume",
    "high": "high",
    "low": "low",
    "condition": "condition",
}


# Cache list-style detection. ``inspect.signature`` is very expensive and was
# previously invoked on *every* builtin call (hot path in nested loops / ta.*).
# Key on the underlying function object (bound methods share ``__func__``).
_LIST_STYLE_HANDLER_CACHE: dict[object, bool] = {}


def _is_list_style_handler(handler: Callable) -> bool:
    """True when the handler expects a single ``args`` list (mixin style).

    Bound methods from BuiltinEvaluator mixins are ``(self, args)`` → after
    bind the remaining parameter is named ``args``. Plain functions like
    ``color_rgb(r, g, b, a=255)`` have multiple named params and need ``*args``.
    """
    cache_key: object = getattr(handler, "__func__", handler)
    try:
        return _LIST_STYLE_HANDLER_CACHE[cache_key]
    except KeyError:
        pass
    except TypeError:
        # Unhashable callable — fall through without caching.
        cache_key = None  # type: ignore[assignment]

    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        result = True
    else:
        params = [
            p
            for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            and p.name != "self"
        ]
        if not params:
            result = False
        else:
            # Mixin handlers always take a leading ``args`` / ``_args`` list;
            # some also accept kwargs.
            result = params[0].name in {"args", "_args"}

    if cache_key is not None:
        _LIST_STYLE_HANDLER_CACHE[cache_key] = result
    return result


class BuiltinDispatchMixin:
    """Shared dispatch utilities for built-in evaluators."""

    _builtin_dispatch: dict[str, BuiltinHandler] | None = None

    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {}

    def _call_builtin(self, name: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        # Resolved-handler cache: (tag, handler) keyed by name.
        # tag 0 = constant, 1 = list-style (args,), 2 = plain *args.
        # Cuts dispatch.get + _is_list_style_handler on every bar after first hit.
        # Pre-allocated on BaseEvaluator; getattr for partial mixin tests.
        resolved = getattr(self, "_builtin_resolved", None)
        if resolved is None:
            resolved = {}
            self._builtin_resolved = resolved  # type: ignore[attr-defined]
        entry = resolved.get(name)

        if entry is None:
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
            if not callable(handler):
                entry = (0, handler)
            elif _is_list_style_handler(handler):
                entry = (1, handler)
            else:
                entry = (2, handler)
            resolved[name] = entry
        tag, handler = entry
        # Constant values registered in the map (e.g. color.red, strategy.long)
        if tag == 0:
            return handler
        if kwargs:
            # Some handlers accept (args, kwargs) directly
            # (e.g. _as_builtin_handler which wraps indicator/strategy).
            # Others like _handle_input_int only accept a single args list.
            # Only soft-retry signature mismatches; body TypeErrors fail closed.
            try:
                return handler(args, kwargs)
            except TypeError as e:
                if e.__traceback__ is not None and e.__traceback__.tb_next is not None:
                    raise
            # Plain functions (color.rgb, etc.): unpack kwargs by signature
            if tag == 2:
                try:
                    return handler(*args, **kwargs)
                except TypeError as e:
                    if e.__traceback__ is not None and e.__traceback__.tb_next is not None:
                        raise
            # Fallback: merge kwargs into positional args for list-style handlers
            bare = name[3:] if name.startswith("ta.") else name
            merged = _merge_kwargs_into_args(args, kwargs, handler, ta_bare=bare)
            if tag == 1:
                return handler(merged)
            return handler(*merged)
        # Positional-only hot path (ta.sma, plot, …)
        if tag == 1:
            return handler(args)
        return handler(*args)

    @staticmethod
    def _error(message: str) -> NoReturn:
        raise ValueError(message)

    def _expect_int(self, value: Any, message: str) -> int:
        """Canonical int coerce for builtins (periods, offsets, indices).

        Defined on the dispatch base so all mixins share one implementation
        (avoids MRO shadowing with weaker copies). Fast path for plain int.
        """
        return pine_expect_int(value, message, self._error)


def _merge_kwargs_into_args(
    args: list[Any],
    kwargs: dict[str, Any],
    handler: Callable,
    *,
    ta_bare: str | None = None,
) -> list[Any]:
    """Merge keyword arguments into the positional args list.

    Inspects the handler's signature to map keyword names to positional
    indices. Falls back to checking for a ``_KWARG_ORDER`` attribute on
    the handler (used by ``input.*`` functions whose signature is just
    ``(self, args)`` but whose first positional argument is ``defval``).

    For ``ta.*`` list-style handlers, uses :data:`_TA_KWARG_ORDERS` so calls
    like ``ta.ema(source=close, length=20)`` become positional ``[close, 20]``.
    Unknown kwargs (plot-style leaks) are dropped for ta handlers.
    """
    try:
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        start = 1 if params and params[0].name == "self" else 0
        param_names = [p.name for p in params[start:]]
    except (ValueError, TypeError):
        param_names = []

    # List-style handlers ``(args)`` / ``(_args)`` are not real parameter
    # names for Pine kwargs — fall through to _KWARG_ORDER / ta orders.
    if len(param_names) == 1 and param_names[0] in {"args", "_args"}:
        param_names = []

    if not param_names:
        # Check for a _KWARG_ORDER attribute on the handler (bound methods
        # store it on the underlying function via __func__).
        kwarg_order: list[str] | None = getattr(handler, "_KWARG_ORDER", None)
        if kwarg_order is None:
            kwarg_order = getattr(getattr(handler, "__func__", None), "_KWARG_ORDER", None)
        # ta.* canonical orders (source=, length=, mult=, …)
        if kwarg_order is None and ta_bare is not None:
            kwarg_order = _TA_KWARG_ORDERS.get(ta_bare)
        if kwarg_order:
            merged = list(args)
            for key, val in kwargs.items():
                canon = _TA_KWARG_ALIASES.get(key, key)
                if canon in kwarg_order:
                    idx = kwarg_order.index(canon)
                    while len(merged) <= idx:
                        merged.append(None)
                    # Don't overwrite an already-provided positional
                    if idx < len(args) and args[idx] is not None:
                        continue
                    merged[idx] = val
                # else: drop unknown ta kwargs (color=, title=, …)
            # Trim trailing Nones introduced by sparse kwargs
            while merged and merged[-1] is None:
                merged.pop()
            return merged
        # Non-ta: append unknown values (legacy behavior)
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
