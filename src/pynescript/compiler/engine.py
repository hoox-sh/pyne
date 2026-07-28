# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Pine → Numba compile-and-run engine.

Pipeline:
  source  →  parse  →  CompilerVisitor.transpile  →  exec  →  njit callable

Use :func:`compile_script` then :meth:`CompiledScript.run` with OHLCV arrays.
Falls back with a clear error if ``numba`` is unavailable.
"""

from __future__ import annotations

import hashlib

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

# Bounded cache: source sha256 → CompiledScript (populated after class defined)
_COMPILE_CACHE: dict[str, Any] = {}
_COMPILE_CACHE_MAX = 32


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
        o = np.asarray(open_, dtype=np.float64)
        h = np.asarray(high, dtype=np.float64)
        l = np.asarray(low, dtype=np.float64)
        c = np.asarray(close, dtype=np.float64)
        if volume is None:
            v = np.ones(len(c), dtype=np.float64)
        else:
            v = np.asarray(volume, dtype=np.float64)
        n = len(c)
        if not (len(o) == len(h) == len(l) == n == len(v)):
            msg = "OHLCV arrays must have the same length"
            raise ValueError(msg)
        raw = self.execute(o, h, l, c, v)
        return _normalize_result(raw)


def _normalize_result(raw: Any) -> dict[str, Any]:
    """Convert numba typed dict / mapping / None into plain dict.

    Plot series become ``float64`` arrays. ``__drawings`` (object-mode) is
    passed through as a Python list of event dicts.
    """
    if raw is None:
        return {}
    try:
        items = raw.items()
    except Exception:
        return {"plot": np.asarray(raw, dtype=np.float64)}
    out: dict[str, Any] = {}
    for k, v in items:
        key = str(k)
        if key == "__drawings":
            out[key] = list(v) if v is not None else []
            continue
        try:
            out[key] = np.asarray(v, dtype=np.float64)
        except (TypeError, ValueError):
            out[key] = v
    return out


def compile_script(source: str, *, use_cache: bool = True) -> CompiledScript:
    """Transpile Pine source and load the compiled entry point.

    Uses Numba when the script is pure-numeric; object-mode (UDT/map/drawing)
    uses a pure-Python numpy bar loop (still much faster than AST walking).

    Results are cached by source hash (max 32) so repeated ``Runtime.run(...,
    mode="compile")`` of the same script skips re-transpile and re-JIT warm-up.
    """
    cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if use_cache and cache_key in _COMPILE_CACHE:
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

    # Warm-up (JIT or first-run)
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
                _COMPILE_CACHE.pop(next(iter(_COMPILE_CACHE)))
            except StopIteration:
                pass
        _COMPILE_CACHE[cache_key] = compiled
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
