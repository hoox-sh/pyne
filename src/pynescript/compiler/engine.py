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

"""Pine → Numba compile-and-run engine.

Pipeline:
  source  →  parse  →  CompilerVisitor.transpile  →  exec  →  njit callable

Use :func:`compile_script` then :meth:`CompiledScript.run` with OHLCV arrays.
Falls back with a clear error if ``numba`` is unavailable.
"""

from __future__ import annotations

import hashlib

from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable

import numpy as np

from pynescript.ast.helper import parse
from pynescript.compiler.compiler import CompilerVisitor

try:
    import numba  # noqa: F401

    _HAS_NUMBA = True
except ImportError:  # pragma: no cover
    _HAS_NUMBA = False

# LRU cache: source sha256 → CompiledScript (populated after class defined)
_COMPILE_CACHE: OrderedDict[str, Any] = OrderedDict()
_COMPILE_CACHE_MAX = 128


def has_numba() -> bool:
    return _HAS_NUMBA


def clear_compile_cache() -> None:
    """Drop all cached compiled scripts (tests / hot-reload)."""
    _COMPILE_CACHE.clear()


def transpile(source: str) -> str:
    """Parse Pine source and return generated Python/Numba source string."""
    tree = parse(source, mode="exec")
    visitor = CompilerVisitor()
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise RuntimeError(msg)
    return code


def _as_f64(x: np.ndarray | list[float]) -> np.ndarray:
    """Convert to contiguous float64 without copying when already correct."""
    if isinstance(x, np.ndarray) and x.dtype == np.float64 and x.flags.c_contiguous:
        return x
    return np.asarray(x, dtype=np.float64)


@dataclass
class CompiledScript:
    """A compiled Pine script ready to run over OHLCV arrays."""

    source: str
    generated_code: str
    execute: Callable[..., Any]
    plot_titles: list[str] = field(default_factory=list)
    object_mode: bool = False

    def run(
        self,
        open_: np.ndarray | list[float],
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
        volume: np.ndarray | list[float] | None = None,
    ) -> dict[str, Any]:
        """Execute over full series; returns plots (+ optional ``__drawings``)."""
        o = _as_f64(open_)
        h = _as_f64(high)
        l = _as_f64(low)
        c = _as_f64(close)
        if volume is None:
            v = np.ones(len(c), dtype=np.float64)
        else:
            v = _as_f64(volume)
        n = len(c)
        if not (len(o) == len(h) == len(l) == n == len(v)):
            msg = "OHLCV arrays must have the same length"
            raise ValueError(msg)
        raw = self.execute(o, h, l, c, v)
        return self._pack_result(raw)

    def _pack_result(self, raw: Any) -> dict[str, Any]:
        """Map execute() output to the public plot-title dict.

        Numeric mode returns a tuple of plot arrays (avoids Numba typed.Dict).
        Object mode still returns a mapping (drawings / strategy extras).
        """
        if isinstance(raw, tuple):
            out: dict[str, Any] = {}
            for i, title in enumerate(self.plot_titles):
                if i >= len(raw):
                    break
                out[title] = _coerce_plot_array(raw[i])
            return out
        return _normalize_result(raw)


def _coerce_plot_array(v: Any) -> Any:
    """Ensure plot series are float64 arrays without redundant copies."""
    if isinstance(v, np.ndarray):
        if v.dtype == np.float64:
            return v
        try:
            return v.astype(np.float64, copy=False)
        except (TypeError, ValueError):
            return v
    try:
        return np.asarray(v, dtype=np.float64)
    except (TypeError, ValueError):
        return v


def _normalize_result(raw: Any) -> dict[str, Any]:
    """Convert numba typed dict / mapping / None into plain dict.

    Plot series become ``float64`` arrays. ``__drawings`` (object-mode) is
    passed through as a Python list of event dicts.
    """
    if raw is None:
        return {}
    if isinstance(raw, tuple):
        # Bare tuple without titles context — index keys (legacy / direct call)
        return {f"plot_{i}": _coerce_plot_array(v) for i, v in enumerate(raw)}
    try:
        items = raw.items()
    except Exception:
        return {"plot": _coerce_plot_array(raw)}
    out: dict[str, Any] = {}
    for k, v in items:
        key = str(k)
        if key in ("__drawings", "__events"):
            out[key] = list(v) if v is not None else []
            continue
        if key.startswith("__") and not isinstance(v, (list, np.ndarray)):
            # strategy scalars: __equity, __netprofit, __position_size
            out[key] = v
            continue
        out[key] = _coerce_plot_array(v)
    return out


def compile_script(source: str, *, use_cache: bool = True) -> CompiledScript:
    """Transpile Pine source and load the compiled entry point.

    Uses Numba when the script is pure-numeric; object-mode (UDT/map/drawing)
    uses a pure-Python numpy bar loop (still much faster than AST walking).

    Results are cached by source hash (max 128, LRU) so repeated
    ``Runtime.run(..., mode="compile")`` of the same script skips re-transpile
    and re-JIT warm-up.
    """
    cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if use_cache and cache_key in _COMPILE_CACHE:
        _COMPILE_CACHE.move_to_end(cache_key)
        return _COMPILE_CACHE[cache_key]

    tree = parse(source, mode="exec")
    visitor = CompilerVisitor()
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise RuntimeError(msg)

    object_mode = bool(visitor.object_mode)
    if not object_mode and not _HAS_NUMBA:
        msg = "numba is required for numeric compile mode (pip install numba)"
        raise RuntimeError(msg)

    titles = [p.get("title", f"Plot {i}") for i, p in enumerate(visitor.plots)]

    namespace: dict[str, Any] = {"__name__": "pynescript_compiled"}
    exec(code, namespace)  # noqa: S102 — intentional compile pipeline
    fn = namespace.get("execute_script_compiled")
    if fn is None or not callable(fn):
        msg = "generated code missing execute_script_compiled()"
        raise RuntimeError(msg)

    # Warm-up JIT only for numeric mode (object mode is pure Python).
    if not object_mode:
        dummy = np.arange(16, dtype=np.float64)
        try:
            fn(dummy, dummy, dummy, dummy, dummy)
        except Exception:
            pass

    compiled = CompiledScript(
        source=source,
        generated_code=code,
        execute=fn,
        plot_titles=titles,
        object_mode=object_mode,
    )
    if use_cache:
        if len(_COMPILE_CACHE) >= _COMPILE_CACHE_MAX:
            try:
                _COMPILE_CACHE.popitem(last=False)
            except KeyError:
                pass
        _COMPILE_CACHE[cache_key] = compiled
        _COMPILE_CACHE.move_to_end(cache_key)
    return compiled


def run_script(
    source: str,
    open_: np.ndarray | list[float],
    high: np.ndarray | list[float],
    low: np.ndarray | list[float],
    close: np.ndarray | list[float],
    volume: np.ndarray | list[float] | None = None,
) -> dict[str, np.ndarray]:
    """One-shot compile + run (re-compiles every call — prefer :func:`compile_script`)."""
    return compile_script(source).run(open_, high, low, close, volume)
