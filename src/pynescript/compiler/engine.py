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

Pipeline
--------
::

    source → sanitize_corpus_source (best-effort)
           → parse
           → CompilerVisitor.transpile (numeric or object)
           → exec → execute_script_compiled
           → (numeric) warm-up njit; on TypingError → re-emit object mode
           → CompiledScript

Entry points
------------
- :func:`transpile` — parse + emit source string only (no exec / JIT).
- :func:`compile_script` — full pipeline + LRU cache (sha256 of sanitized source).
- :func:`run_script` — one-shot compile + :meth:`CompiledScript.run`.
- :class:`CompiledScript` — holds generated code and the callable.

Interpret vs compile contracts
------------------------------
- **Input OHLCV**: equal-length float64 series (lists coerced). Missing volume →
  ones. Mismatched lengths → ``ValueError("OHLCV arrays must have the same length")``.
- **Return shape** (``CompiledScript.run``):
  - Numeric mode: ``dict[plot_title, float64 ndarray]`` (from a plot tuple; titles
    come from ``CompilerVisitor.plots``).
  - Object mode: same plot keys **plus** optional ``__drawings`` (list of event
    dicts), and when strategy is used ``__events``, ``__position_size``,
    ``__netprofit``, ``__equity``.
  - Bare / legacy mappings may also carry other ``__*`` strategy scalars.
- **Numba**: required only for pure-numeric mode. Object mode is pure Python +
  numpy (still faster than AST interpret). Missing numba on a numeric emit raises
  ``RuntimeError("numba is required for numeric compile mode …")``.
- **Errors**: empty emit / missing ``execute_script_compiled`` → ``RuntimeError``.
  nopython failures during warm-up are **not** raised; the engine falls back to
  object mode. Non-nopython errors on warm-up are deferred to the first real run.
- **Sanitize-on-compile**: scraped corpus chrome is stripped via
  ``pynescript.util.corpus_sanitize.sanitize_corpus_source`` (same policy as
  interpret paths). Failures are ignored.

Cache
-----
In-process LRU (max 128) keyed by sha256 of the **sanitized** source.
Secondary IR cache (max 64) keyed by sha256 of **generated Python** so
comment-only / whitespace-only source variants reuse the same warm njit
callable without re-JIT. :func:`clear_compile_cache` clears both.
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
# Secondary: generated-code sha256 → CompiledScript (share JIT across sources)
_IR_CACHE: OrderedDict[str, Any] = OrderedDict()
_IR_CACHE_MAX = 64
_BUILTINS_WARMED = False


def has_numba() -> bool:
    """Return whether Numba is importable in this process.

    Numeric compile mode requires Numba. Object mode (UDT/map/drawing/strategy)
    does not. Callers use this for capability checks before advertising compile.
    """
    return _HAS_NUMBA


def clear_compile_cache() -> None:
    """Drop all cached compiled scripts (tests / hot-reload)."""
    _COMPILE_CACHE.clear()
    _IR_CACHE.clear()


def _warm_common_numba_builtins() -> None:
    """JIT-compile the hottest shared kernels once per process.

    Generated ``execute_script_compiled`` still JITs per IR, but first-touch
    cost of ``numba_sma_inc`` / ``numba_ema_inc`` / … is paid only once when
    many distinct scripts share the same builtins.
    """
    global _BUILTINS_WARMED
    if _BUILTINS_WARMED or not _HAS_NUMBA:
        return
    _BUILTINS_WARMED = True
    try:
        from pynescript.compiler import numba_builtins as nb

        a = np.arange(32, dtype=np.float64)
        st2 = np.full(2, np.nan)
        st3 = np.full(3, np.nan)
        st4 = np.full(4, np.nan)
        st7 = np.full(7, np.nan)
        raw = np.full(32, np.nan)
        raw2 = np.full(32, np.nan)
        for i in range(32):
            nb.numba_sma_inc(a, 5, i, st2)
            nb.numba_ema_inc(a, 5, i, st2)
            nb.numba_rsi_inc(a, 5, i, st3)
            nb.numba_stdev_inc(a, 5, i, st3)
            nb.numba_sum_inc(a, 5, i, st2)
            nb.numba_wma_inc(a, 5, i, st3)
            nb.numba_swma(a, i)
            nb.numba_dema_inc(a, 5, i, st3, raw)
            nb.numba_tema_inc(a, 5, i, st4, raw, raw2)
            nb.numba_hma_inc(a, 9, i, st7, raw)
            nb.numba_change(a, 1, i)
            nb.numba_nz(float(i), 0.0)
    except Exception:
        # Warm-up is best-effort; real compile path surfaces real errors.
        pass


def transpile(source: str) -> str:
    """Parse Pine source and return generated Python/Numba source string.

    Does **not** sanitize, exec, JIT, or cache. Useful for debugging the emitter.
    Empty visitor output raises ``RuntimeError``.
    """
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
    """A compiled Pine script ready to run over OHLCV arrays.

    Attributes
    ----------
    source:
        Original Pine source (post-sanitize when produced by :func:`compile_script`).
    generated_code:
        Full Python module text (imports + UDFs + ``execute_script_compiled``).
    execute:
        Bound ``execute_script_compiled(open, high, low, close, volume)`` callable.
        Numeric mode is an ``@numba.njit`` function; object mode is plain Python.
    plot_titles:
        Ordered titles used to map numeric-mode tuple returns onto dict keys.
    object_mode:
        ``True`` when the emit path (or nopython fallback) used the pure-Python
        bar loop. Controls packing only indirectly — the callable already matches.
    """

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
        """Execute over full series; returns plots (+ optional ``__drawings`` / strategy).

        Coerces inputs to float64, defaults volume to ones, validates equal lengths,
        then :meth:`_pack_result` on the raw ``execute`` return value.
        """
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


def _is_numba_nopython_failure(exc: BaseException) -> bool:
    """True when *exc* looks like a Numba nopython / typing failure.

    Used to re-emit object mode when pure-numeric njit cannot accept the
    generated code (pyobject arrays, unicode ``isnan``, missing impls, …).
    """
    name = type(exc).__name__
    if name in ("TypingError", "NumbaError", "NumbaTypeError", "LoweringError"):
        return True
    msg = str(exc)
    markers = (
        "Failed in nopython mode",
        "non-precise type array(pyobject",
        "No implementation of function",
        "cannot determine Numba type",
        "TypingError",
        "isnan(unicode_type)",
        "unicode_type",
        "array(pyobject",
    )
    return any(m in msg for m in markers)


def _transpile_once(
    source: str,
    *,
    force_object_mode: bool = False,
) -> tuple[str, list[str], bool]:
    """Parse + emit. Returns ``(generated_code, plot_titles, object_mode)``."""
    tree = parse(source, mode="exec")
    visitor = CompilerVisitor(force_object_mode=force_object_mode)
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise RuntimeError(msg)
    object_mode = bool(visitor.object_mode) or force_object_mode
    titles = [p.get("title", f"Plot {i}") for i, p in enumerate(visitor.plots)]
    return code, titles, object_mode


def _exec_generated(
    source: str,
    code: str,
    titles: list[str],
    object_mode: bool,
) -> CompiledScript:
    """Exec generated module text and bind ``execute_script_compiled``."""
    if not object_mode and not _HAS_NUMBA:
        msg = "numba is required for numeric compile mode (pip install numba)"
        raise RuntimeError(msg)

    if not object_mode:
        _warm_common_numba_builtins()

    namespace: dict[str, Any] = {"__name__": "pynescript_compiled"}
    exec(code, namespace)  # noqa: S102 — intentional compile pipeline
    fn = namespace.get("execute_script_compiled")
    if fn is None or not callable(fn):
        msg = "generated code missing execute_script_compiled()"
        raise RuntimeError(msg)

    return CompiledScript(
        source=source,
        generated_code=code,
        execute=fn,
        plot_titles=titles,
        object_mode=object_mode,
    )


def _compile_once(
    source: str,
    *,
    force_object_mode: bool = False,
) -> CompiledScript:
    """Parse → transpile → exec once. Internal helper for :func:`compile_script`.

    When *force_object_mode* is true, :class:`CompilerVisitor` pins object emit
    (nopython recovery path). Requires Numba only if the result stays numeric.
    """
    code, titles, object_mode = _transpile_once(
        source, force_object_mode=force_object_mode
    )
    return _exec_generated(source, code, titles, object_mode)


def _cache_put(cache: OrderedDict[str, Any], key: str, value: Any, maxsize: int) -> None:
    if len(cache) >= maxsize and key not in cache:
        try:
            cache.popitem(last=False)
        except KeyError:
            pass
    cache[key] = value
    cache.move_to_end(key)


def _share_compiled(source: str, base: CompiledScript) -> CompiledScript:
    """Clone cache entry for a new source string sharing the same IR / execute."""
    return CompiledScript(
        source=source,
        generated_code=base.generated_code,
        execute=base.execute,
        plot_titles=list(base.plot_titles),
        object_mode=base.object_mode,
    )


def compile_script(source: str, *, use_cache: bool = True) -> CompiledScript:
    """Transpile Pine source and load the compiled entry point.

    Uses Numba when the script is pure-numeric; object-mode (UDT/map/drawing)
    uses a pure-Python numpy bar loop (still much faster than AST walking).

    If nopython JIT warm-up fails (pyobject arrays, unicode ops, …), re-emits
    the same script in object mode so ``mode=compile`` still runs.

    Results are cached by source hash (max 128, LRU) so repeated
    ``Runtime.run(..., mode="compile")`` of the same script skips re-transpile
    and re-JIT warm-up. A secondary IR cache (max 64) reuses an already-warm
    ``execute`` when two sources emit identical generated code (e.g. comment
    diffs), avoiding a second cold njit of the same entry.

    Scraped corpus sources are sanitized first (same as parse/runtime interpret)
    so docs chrome / Expand stubs do not fail compile-only paths.
    """
    try:
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        source = sanitize_corpus_source(source)
    except Exception:
        pass
    cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if use_cache and cache_key in _COMPILE_CACHE:
        _COMPILE_CACHE.move_to_end(cache_key)
        return _COMPILE_CACHE[cache_key]

    code, titles, object_mode = _transpile_once(source, force_object_mode=False)
    ir_key = hashlib.sha256(code.encode("utf-8")).hexdigest()

    # Same generated IR as a prior script → reuse warm njit callable.
    if use_cache and ir_key in _IR_CACHE:
        compiled = _share_compiled(source, _IR_CACHE[ir_key])
        _cache_put(_COMPILE_CACHE, cache_key, compiled, _COMPILE_CACHE_MAX)
        _IR_CACHE.move_to_end(ir_key)
        return compiled

    compiled = _exec_generated(source, code, titles, object_mode)

    # Warm-up JIT only for numeric mode (object mode is pure Python).
    if not compiled.object_mode:
        dummy = np.arange(16, dtype=np.float64)
        try:
            compiled.execute(dummy, dummy, dummy, dummy, dummy)
        except Exception as exc:
            if _is_numba_nopython_failure(exc):
                # Structural recovery: re-emit pure-Python object bar loop.
                code_o, titles_o, _ = _transpile_once(source, force_object_mode=True)
                compiled = _exec_generated(source, code_o, titles_o, True)
                ir_key = hashlib.sha256(code_o.encode("utf-8")).hexdigest()
            # else: leave as-is; first real run will surface the error

    if use_cache:
        _cache_put(_COMPILE_CACHE, cache_key, compiled, _COMPILE_CACHE_MAX)
        _cache_put(_IR_CACHE, ir_key, compiled, _IR_CACHE_MAX)
    return compiled


def run_script(
    source: str,
    open_: np.ndarray | list[float],
    high: np.ndarray | list[float],
    low: np.ndarray | list[float],
    close: np.ndarray | list[float],
    volume: np.ndarray | list[float] | None = None,
) -> dict[str, np.ndarray]:
    """One-shot compile + run (re-compiles every call — prefer :func:`compile_script`).

    Return type annotation is the common plot map; object-mode may also include
    non-array extras (``__drawings``, strategy fields) as documented on
    :meth:`CompiledScript.run`.
    """
    return compile_script(source).run(open_, high, low, close, volume)
