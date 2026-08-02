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
import numbers

from collections.abc import Callable
from typing import Any
from typing import NoReturn


BuiltinHandler = Callable[[list[Any]], Any]

# Floats within this of an integer coerce via int(round(...)) (TV length floats
# like ``14.0`` / ``14.0000000001``). Larger fractions floor (``14.9`` → ``14``).
_PERIOD_INT_EPS = 1e-9


def _is_na_scalar(value: Any) -> bool:
    """True for Pine ``na``: ``None``, NaN float, or ``_NaValue`` wrapper."""
    if value is None or type(value).__name__ == "_NaValue":
        return True
    if type(value) is float:
        return math.isnan(value)
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        try:
            return math.isnan(float(value))
        except (TypeError, ValueError):
            return False
    return False


def _series_current(value: Any) -> Any:
    """``PineSeries`` / ``_SeriesResult`` current sample (history fallback)."""
    if type(value).__name__ == "_NaValue":
        return value
    cur = value.current
    if cur is not None or not hasattr(value, "history"):
        return cur
    hist = value.history
    if not hist:
        return cur
    try:
        # deque (newest-first) → [0]; list history may be chronological
        return hist[0] if not isinstance(hist, list) else hist[-1]
    except (IndexError, TypeError, KeyError):
        return cur


def _unwrap_period_value(value: Any) -> Any:
    """Unwrap input dicts, series wrappers, and list/tuple last-samples once.

    Does not coerce to int — caller decides na / numeric handling. Series lists
    are chronological (oldest first) → last element is current bar. PineSeries
    / ``_SeriesResult`` prefer ``.current``; if that is ``None`` but history is
    non-empty, use newest history sample (``history[0]`` for deque, last for list).
    """
    if type(value) is dict and "default" in value:
        value = value["default"]

    if not isinstance(value, (list, tuple, str, bytes)) and hasattr(value, "current"):
        value = _series_current(value)

    t = type(value)
    if t is list or t is tuple:
        if not value:
            return value  # empty — caller errors
        value = value[-1]
        if not isinstance(value, (list, tuple, str, bytes)) and hasattr(value, "current"):
            value = _series_current(value)
    return value


def _float_to_period_int(value: float) -> int:
    """Coerce a finite float length to int (near-integer → round, else floor)."""
    nearest = round(value)
    if abs(value - nearest) <= _PERIOD_INT_EPS:
        return int(nearest)
    return math.floor(value)


def _coerce_real_period(value: Any, message: str, error: Callable[[str], NoReturn]) -> int:
    """Coerce float / numbers.Real / numeric str to period int."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        if type(value) is str:
            error(f"{message}. Got: str {value!r}")
        error(f"{message}. Got: {type(value).__name__}")
    if math.isnan(f):
        error(f"{message}. Got: na")
    if math.isinf(f):
        error(f"{message}. Got: float inf")
    return _float_to_period_int(f)


def pine_expect_int(value: Any, message: str, error: Callable[[str], NoReturn]) -> int:
    """Coerce a Pine value to ``int`` (periods, offsets, indices).

    Hot path: plain ``int`` (not ``bool``) returns immediately — TA periods and
    plot offsets hit this every bar. Unwraps series wrappers, input dicts, and
    list/tuple last-samples; finite floats near an integer use ``int(round)``,
    other finite floats floor (TV length semantics). Accepts ``numbers.Integral``
    / ``numbers.Real`` (e.g. numpy scalars).

    Raises via *error* with ``Got: <type|na|…>`` so type bugs surface clearly
    instead of a bare message (or silent wrong path). ``na`` raises; TA call
    sites that want TV ``na``→``na`` use :func:`pine_period_or_none` /
    ``_expect_series`` instead.
    """
    # Fast path: true int (bool is an int subclass — reject here)
    if type(value) is int:
        return value

    value = _unwrap_period_value(value)

    if type(value) is int:
        return value
    if type(value) is list or type(value) is tuple:
        error(f"{message}. Got: empty series")
    if _is_na_scalar(value):
        error(f"{message}. Got: na")
    if type(value) is bool:
        return int(value)
    # numpy.int64 / other Integral (bool already handled)
    if isinstance(value, numbers.Integral):
        return int(value)
    # float, numpy.float64, numeric strings
    if type(value) is float or type(value) is str or isinstance(value, numbers.Real):
        return _coerce_real_period(value, message, error)

    error(f"{message}. Got: {type(value).__name__}")
    _unreachable = "unreachable"
    raise AssertionError(_unreachable)  # error() is NoReturn; keep type-checkers happy


def pine_period_or_none(value: Any, message: str, error: Callable[[str], NoReturn]) -> int | None:
    """Like :func:`pine_expect_int` but ``na`` → ``None`` (TV TA length na → na).

    Used by TA ``_expect_series`` so ``ta.sma(close, na)`` yields na instead of
    hard-failing.

    Non-numeric *identifier* strings (unresolved names leaked as the name
    text — e.g. ``length``, ``rsiLen`` from incomplete module scrapes) also
    soft-return ``None`` so TA returns na rather than aborting the bar loop.
    Numeric strings (``\"14\"``) still coerce via :func:`pine_expect_int`.
    Other invalid types still raise via *error*.
    """
    if type(value) is int:
        return value
    unwrapped = _unwrap_period_value(value)
    if (type(unwrapped) is list or type(unwrapped) is tuple) and not unwrapped:
        error(f"{message}. Got: empty series")
    if _is_na_scalar(unwrapped):
        return None
    # Unresolved name leak: bare identifier becomes a non-numeric str in context.
    if type(unwrapped) is str:
        s = unwrapped.strip()
        if not s:
            return None
        try:
            float(s)
        except ValueError:
            return None
    return pine_expect_int(unwrapped, message, error)

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

# Cached positional param names for kwargs→args merge (same keying as list-style).
# ``None`` value means "use _KWARG_ORDER / ta orders / append fallback".
_HANDLER_PARAM_NAMES_CACHE: dict[object, list[str] | None] = {}


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


def _handler_param_names(handler: Callable) -> list[str] | None:
    """Return cached positional parameter names for kwargs merge, or None.

    ``None`` means the callee is list-style / uninspectable and the caller
    should use ``_KWARG_ORDER`` / ``_TA_KWARG_ORDERS`` instead of inspect.
    """
    cache_key: object = getattr(handler, "__func__", handler)
    try:
        return _HANDLER_PARAM_NAMES_CACHE[cache_key]
    except KeyError:
        pass
    except TypeError:
        cache_key = None  # type: ignore[assignment]

    param_names: list[str] | None
    try:
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        start = 1 if params and params[0].name == "self" else 0
        names = [p.name for p in params[start:]]
    except (ValueError, TypeError):
        names = []

    # List-style handlers ``(args)`` / ``(_args)`` are not real Pine params.
    if len(names) == 1 and names[0] in {"args", "_args"}:
        param_names = None
    elif not names:
        param_names = None
    else:
        param_names = names

    if cache_key is not None:
        _HANDLER_PARAM_NAMES_CACHE[cache_key] = param_names
    return param_names


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
                # Empty name is never a real typo — it comes from dual-mode
                # attribute chains that resolved to an empty string (e.g.
                # ``syminfo.prefix`` property ``""`` then called as a function
                # before dual-mode registration). Soft-fail to na.
                if not name:
                    return None
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
            # IMPORTANT: list-style (tag 1) vs plain (tag 2) must not share the
            # same first attempt. Plain functions like ``color.new(color, transp)``
            # accept ``*extra, **kwargs`` so ``handler(args_list, kwargs_dict)``
            # *binds successfully* with color=the whole args list — then body
            # ``int(color)`` raises TypeError. Round-6 fail-closed would re-raise
            # that body error and never reach ``handler(*args, **kwargs)``.
            # Camarilla++: ``color.new(color.white, transp=75)`` hit this path.
            if tag == 1:
                # Mixin handlers: (args, kwargs) or (args,) after merge.
                # Prefer merge-first when the handler declares _KWARG_ORDER or a
                # ta.* order table — avoids raising TypeError on every
                # ``array.set(id=…, index=…, value=…)`` (DFT / UDT-heavy scripts).
                bare = name[3:] if name.startswith("ta.") else name
                kw_order = getattr(handler, "_KWARG_ORDER", None)
                if kw_order is None:
                    kw_order = getattr(getattr(handler, "__func__", None), "_KWARG_ORDER", None)
                if kw_order is not None or (bare and bare in _TA_KWARG_ORDERS):
                    merged = _merge_kwargs_into_args(args, kwargs, handler, ta_bare=bare)
                    return handler(merged)
                try:
                    return handler(args, kwargs)
                except TypeError as e:
                    # Signature mismatch only (no callee body frame) → merge
                    if e.__traceback__ is not None and e.__traceback__.tb_next is not None:
                        raise
                merged = _merge_kwargs_into_args(args, kwargs, handler, ta_bare=bare)
                return handler(merged)
            # Plain functions (color.new, color.rgb, math.*, …): *args, **kwargs
            try:
                return handler(*args, **kwargs)
            except TypeError as e:
                if e.__traceback__ is not None and e.__traceback__.tb_next is not None:
                    raise
            bare = name[3:] if name.startswith("ta.") else name
            merged = _merge_kwargs_into_args(args, kwargs, handler, ta_bare=bare)
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


def _merge_via_kwarg_order(
    args: list[Any],
    kwargs: dict[str, Any],
    kwarg_order: list[str],
) -> list[Any]:
    """Place kwargs into positions named by *kwarg_order* (list-style handlers)."""
    merged = list(args)
    # Indices filled by an explicit keyword (including value=None / Pine na).
    # Trailing-None trim must not drop those — e.g. array.push(id=a, value=na)
    # would otherwise collapse to [a] and fail arity checks.
    explicit_idx: set[int] = set()
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
            explicit_idx.add(idx)
        # else: drop unknown ta/plot kwargs (color=, title=, …)
    # Trim trailing Nones introduced only as sparse padding slots
    while merged and merged[-1] is None and (len(merged) - 1) not in explicit_idx:
        merged.pop()
    return merged


def _merge_kwargs_into_args(
    args: list[Any],
    kwargs: dict[str, Any],
    handler: Callable,
    *,
    ta_bare: str | None = None,
) -> list[Any]:
    """Merge keyword arguments into the positional args list.

    Order of resolution (cheap → expensive):

    1. Handler ``_KWARG_ORDER`` (array.*, input.*, timestamp, …)
    2. ``_TA_KWARG_ORDERS`` for ``ta.*`` bare names
    3. Cached ``inspect.signature`` param names (plain Python callables)
    4. Append kwargs values (legacy non-ta fallback)

    ``inspect.signature`` is never called more than once per handler object
    (see :func:`_handler_param_names`). Hot corpus paths
    (``array.set(id=…, index=…, value=…)``, complex DFT helpers) used to pay
    full signature introspection on every call.
    """
    # Prefer explicit kwarg order on mixin handlers — no inspect needed.
    kwarg_order: list[str] | None = getattr(handler, "_KWARG_ORDER", None)
    if kwarg_order is None:
        kwarg_order = getattr(getattr(handler, "__func__", None), "_KWARG_ORDER", None)
    if kwarg_order is None and ta_bare is not None:
        kwarg_order = _TA_KWARG_ORDERS.get(ta_bare)
    if kwarg_order:
        return _merge_via_kwarg_order(args, kwargs, kwarg_order)

    param_names = _handler_param_names(handler)
    if not param_names:
        # Non-ta list-style without order table: append values (legacy).
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
