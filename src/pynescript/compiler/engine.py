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

    source → (memory LRU hit by raw or sanitized sha256)
           → sanitize_corpus_source (best-effort; miss path only)
           → (optional disk source→IR index hit)
           → parse + CompilerVisitor.transpile
           → (IR LRU hit → share warm execute)
           → exec / import disk module → execute_script_compiled
           → (numeric) warm-up njit; on TypingError → re-emit object mode
           → CompiledScript

Entry points
------------
- :func:`transpile` — parse + emit source string only (no exec / JIT).
- :func:`compile_script` — full pipeline + LRU cache (sha256 of source).
- :func:`run_script` — one-shot compile + :meth:`CompiledScript.run`.
- :func:`prewarm_numba_builtins` / :func:`prewarm_scripts` — host cold-start hooks.
- :func:`ensure_compile_cache_dir` / :func:`compile_deploy_config` — deploy knobs.
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
  :class:`CompileNumbaRequiredError`.
- **Errors**: empty emit / missing ``execute_script_compiled`` →
  :class:`CompileEmitError` / :class:`CompileLoadError`. nopython failures
  during warm-up are **not** raised; the engine falls back to object mode and
  records :attr:`CompiledScript.nopython_fallback_reason`. Non-nopython errors
  on warm-up are deferred to the first real run (dummy OHLCV may not match
  production data shapes).
- **Sanitize-on-compile**: scraped corpus chrome is stripped via
  ``pynescript.util.corpus_sanitize.sanitize_corpus_source`` (same policy as
  interpret paths). Failures keep the raw source. Cache is probed by **raw**
  hash first so warm hits skip sanitize entirely.

Cache
-----
- In-process source LRU (max 128) keyed by sha256 of **raw and/or sanitized**
  source (dual-key when they differ).
- Secondary IR cache (max 64) keyed by sha256 of **generated Python** so
  comment-only source variants reuse the same warm njit callable.
- Optional **disk** module cache (default on; ``PYNE_COMPILE_DISK_CACHE=0`` to
  disable): writes generated modules under ``PYNE_COMPILE_CACHE_DIR`` or
  ``$XDG_CACHE_HOME/pynescript/compile`` so ``@numba.njit(cache=True)`` can
  reuse machine code across process restarts. :func:`clear_compile_cache`
  clears in-process maps only; :func:`clear_disk_compile_cache` removes disk
  IR/index files (and that tree's ``__pycache__``).
- **Numba function cache** (``.nbi`` / ``.nbc``): written next to
  :mod:`pynescript.compiler.numba_builtins` under
  ``…/compiler/__pycache__/`` and under the disk IR ``__pycache__/`` when
  generated modules use ``@numba.njit(cache=True)``. Truncated/corrupt files
  raise ``EOFError`` / ``pickle.UnpicklingError`` on load; the engine purges
  those artifacts and recompiles instead of failing the script. Manual clear::

      from pynescript.compiler import clear_numba_function_caches, clear_disk_compile_cache
      clear_numba_function_caches()
      clear_disk_compile_cache()
      # or: rm -rf ~/.cache/pynescript/compile \\
      #        src/pynescript/compiler/__pycache__/numba_builtins*.nb*

- Host prewarm (default on via ``PYNE_COMPILE_PREWARM=1``): call
  :func:`prewarm_numba_builtins` / :func:`prewarm_scripts` or Pro API
  ``POST /compile/prewarm`` so the first user request is warm.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import pickle
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
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

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typed exceptions (fail closed / surface cleanly — no silent wrong results)
# ---------------------------------------------------------------------------


class CompileError(RuntimeError):
    """Base class for compile-pipeline failures.

    Hosts (``mode=auto``) catch this family and set ``compile_fallback_reason``.
    Subclasses keep messages stable enough for tests and UI strings.
    """


class CompileEmitError(CompileError):
    """Parser/visitor produced empty or unusable generated code."""


class CompileLoadError(CompileError):
    """Generated module exec/import failed or entry point missing."""


class CompileNumbaRequiredError(CompileError):
    """Numeric mode needs Numba but it is not installed."""


class CompileWarmupError(CompileError):
    """Reserved for forced warm-up failure surfacing (not used for nopython fallback)."""


# LRU cache: source sha256 → CompiledScript
_COMPILE_CACHE: OrderedDict[str, Any] = OrderedDict()
_COMPILE_CACHE_MAX = 128
# Secondary: generated-code sha256 → CompiledScript (share JIT across sources)
_IR_CACHE: OrderedDict[str, Any] = OrderedDict()
_IR_CACHE_MAX = 64
_BUILTINS_WARMED = False

# Disk index schema version (bump when metadata layout changes)
# Bump when generated IR semantics change so source→IR disk index is invalidated
# (source hash alone is stable across compiler fixes, e.g. fill() series keys).
# v4: ta.vwap(hlc3) materialize + anchor reset; prior v3 SYMBOL/tickerid pack
_DISK_META_VERSION = 4
_NJIT_CACHE_FALSE = "@numba.njit(cache=False)"
_NJIT_CACHE_TRUE = "@numba.njit(cache=True)"


def has_numba() -> bool:
    """Return whether Numba is importable in this process.

    Numeric compile mode requires Numba. Object mode (UDT/map/drawing/strategy)
    does not. Callers use this for capability checks before advertising compile.
    """
    return _HAS_NUMBA


def clear_compile_cache() -> None:
    """Drop all **in-process** cached compiled scripts (tests / hot-reload).

    Does **not** remove the optional on-disk module cache — use
    :func:`clear_disk_compile_cache` for that.
    """
    _COMPILE_CACHE.clear()
    _IR_CACHE.clear()


def clear_disk_compile_cache() -> None:
    """Remove generated modules / source index under the disk cache directory.

    Best-effort; missing directory is a no-op. Clears ``.py`` / ``.json`` and
    that tree's ``__pycache__`` (including Numba ``.nbi``/``.nbc`` written for
    disk IR modules). Does **not** clear :mod:`numba_builtins` function caches
    outside this tree — use :func:`clear_numba_function_caches` for those.
    """
    try:
        root = _disk_cache_dir()
    except Exception as exc:  # pragma: no cover
        _log.debug("disk cache dir resolve failed: %s", exc)
        return
    if not root.is_dir():
        return
    for path in root.iterdir():
        try:
            if path.is_file() and (
                path.suffix in {".py", ".json", ".tmp"}
                or path.name.endswith(".py.tmp")
            ):
                path.unlink(missing_ok=True)
            elif path.is_dir() and path.name == "__pycache__":
                for child in path.iterdir():
                    child.unlink(missing_ok=True)
                path.rmdir()
        except OSError as exc:
            _log.debug("disk cache unlink %s failed: %s", path, exc)


def _numba_function_cache_dirs() -> list[Path]:
    """Directories where Numba may write ``.nbi`` / ``.nbc`` for our JIT code."""
    dirs: list[Path] = []
    try:
        # InTreeCacheLocator: …/compiler/__pycache__/numba_builtins.*.nb{i,c}
        from pynescript.compiler import numba_builtins as nb

        nb_path = getattr(nb, "__file__", None)
        if nb_path:
            dirs.append(Path(nb_path).resolve().parent / "__pycache__")
    except Exception as exc:  # pragma: no cover
        _log.debug("numba_builtins cache dir resolve failed: %s", exc)
    try:
        # Disk IR modules with @njit(cache=True) rewrite
        dirs.append(_disk_cache_dir() / "__pycache__")
    except Exception as exc:  # pragma: no cover
        _log.debug("disk IR numba cache dir resolve failed: %s", exc)
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def clear_numba_function_caches() -> int:
    """Remove Numba ``.nbi`` / ``.nbc`` function-cache files under known dirs.

    Targets:

    - ``…/pynescript/compiler/__pycache__/`` (``numba_builtins`` kernels with
      ``@numba.njit(cache=True)``)
    - ``~/.cache/pynescript/compile/__pycache__/`` (disk IR modules rewritten
      to ``cache=True``)

    Used for ops after code changes and by the engine when pickle load fails
    with ``EOFError`` / ``UnpicklingError`` (truncated cache). Returns the
    number of files unlinked (best-effort).
    """
    removed = 0
    for cache_dir in _numba_function_cache_dirs():
        if not cache_dir.is_dir():
            continue
        try:
            children = list(cache_dir.iterdir())
        except OSError as exc:
            _log.debug("numba cache list %s failed: %s", cache_dir, exc)
            continue
        for path in children:
            name = path.name
            if not (name.endswith(".nbi") or name.endswith(".nbc")):
                continue
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError as exc:
                _log.debug("numba cache unlink %s failed: %s", path, exc)
    return removed


def _is_numba_cache_corruption(exc: BaseException) -> bool:
    """True when *exc* looks like a truncated / unreadable Numba disk cache.

    Numba loads ``.nbi``/``.nbc`` via pickle; incomplete files raise
    ``EOFError: Ran out of input`` or ``pickle.UnpicklingError``.
    """
    if isinstance(exc, EOFError):
        return True
    if isinstance(exc, pickle.UnpicklingError):
        return True
    # Some wrappers re-raise as RuntimeError with the original message.
    name = type(exc).__name__
    if name in ("UnpicklingError", "EOFError"):
        return True
    msg = str(exc)
    if "Ran out of input" in msg:
        return True
    if "pickle data was truncated" in msg:
        return True
    if "UnpicklingError" in msg and ("pickle" in msg.lower() or "truncated" in msg):
        return True
    return False


def _call_with_numba_cache_recovery(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Invoke *fn*; on Numba cache pickle failure, purge ``.nb*`` and retry once."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if not _is_numba_cache_corruption(exc):
            raise
        n = clear_numba_function_caches()
        _log.warning(
            "corrupt Numba function cache (%s: %s); purged %d file(s) and recompiling",
            type(exc).__name__,
            exc,
            n,
        )
        return fn(*args, **kwargs)


def _env_truthy(name: str, default: str = "1") -> bool:
    """Parse common env flags; empty / 0 / false / no / off → False."""
    v = os.environ.get(name, default)
    if v is None:
        v = default
    return str(v).strip().lower() not in {"0", "false", "no", "off", ""}


def compile_cache_stats() -> dict[str, Any]:
    """Return in-process cache sizes and prewarm / disk flags (diagnostics)."""
    disk_on = _disk_cache_enabled()
    return {
        "source_entries": len(_COMPILE_CACHE),
        "source_max": _COMPILE_CACHE_MAX,
        "ir_entries": len(_IR_CACHE),
        "ir_max": _IR_CACHE_MAX,
        "builtins_warmed": _BUILTINS_WARMED,
        "disk_cache_enabled": disk_on,
        "disk_cache_dir": str(_disk_cache_dir()) if disk_on else None,
        "prewarm_enabled": prewarm_enabled(),
        "has_numba": _HAS_NUMBA,
    }


def compile_deploy_config() -> dict[str, Any]:
    """Stable deploy knobs for health / ops (no secrets).

    Defaults favor production warm-compile: disk IR cache **on**, host prewarm
    **on** (soft-fail without Numba). Operators opt out via env flags.
    """
    return {
        "disk_cache_enabled": _disk_cache_enabled(),
        "disk_cache_dir": str(_disk_cache_dir()) if _disk_cache_enabled() else None,
        "prewarm_enabled": prewarm_enabled(),
        "has_numba": _HAS_NUMBA,
        "source_cache_max": _COMPILE_CACHE_MAX,
        "ir_cache_max": _IR_CACHE_MAX,
        "default_runtime_mode": "auto",
        "env": {
            "PYNE_COMPILE_DISK_CACHE": os.environ.get("PYNE_COMPILE_DISK_CACHE", "1"),
            "PYNE_COMPILE_CACHE_DIR": os.environ.get("PYNE_COMPILE_CACHE_DIR", "") or None,
            "PYNE_COMPILE_PREWARM": os.environ.get("PYNE_COMPILE_PREWARM", "1"),
        },
    }


def prewarm_enabled() -> bool:
    """Whether host/process prewarm is requested (``PYNE_COMPILE_PREWARM``, default on)."""
    return _env_truthy("PYNE_COMPILE_PREWARM", "1")


def _disk_cache_enabled() -> bool:
    """Opt-out disk module cache: ``PYNE_COMPILE_DISK_CACHE=0|false|no|off``."""
    return _env_truthy("PYNE_COMPILE_DISK_CACHE", "1")


def _disk_cache_dir() -> Path:
    """Resolve disk cache root (env override → XDG → ~/.cache).

    Deploy tip: set ``PYNE_COMPILE_CACHE_DIR=/data/compile-cache`` on a
    persistent volume so IR + Numba ``.nbc`` survive worker restarts.
    """
    env = os.environ.get("PYNE_COMPILE_CACHE_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "pynescript" / "compile"
    return Path.home() / ".cache" / "pynescript" / "compile"


def ensure_compile_cache_dir() -> Path | None:
    """Create the disk compile-cache directory when disk cache is enabled.

    Returns the resolved path, or ``None`` when disk cache is disabled or
    mkdir fails (soft — compile still works with memory-only caches).
    """
    if not _disk_cache_enabled():
        return None
    root = _disk_cache_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError as exc:
        _log.debug("compile cache dir create failed (%s): %s", root, exc)
        return None


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_common_numba_builtin_warm() -> None:
    """Touch hot shared kernels once (may load Numba disk cache)."""
    from pynescript.compiler import numba_builtins as nb

    a = np.arange(32, dtype=np.float64)
    h = a + 1.0
    l = a - 1.0
    st2 = np.full(2, np.nan)
    st3 = np.full(3, np.nan)
    st4 = np.full(4, np.nan)
    st7 = np.full(7, np.nan)
    raw = np.full(32, np.nan)
    raw2 = np.full(32, np.nan)
    for i in range(32):
        nb.numba_sma_inc(a, 5, i, st2)
        nb.numba_ema_inc(a, 5, i, st2.copy())
        nb.numba_rma_inc(a, 5, i, st2.copy())
        nb.numba_rsi_inc(a, 5, i, st3.copy())
        nb.numba_stdev_inc(a, 5, i, st3.copy())
        nb.numba_sum_inc(a, 5, i, st2.copy())
        nb.numba_wma_inc(a, 5, i, st3.copy())
        nb.numba_highest_inc(a, 5, i, st2.copy())
        nb.numba_lowest_inc(a, 5, i, st2.copy())
        nb.numba_atr_inc(h, l, a, 5, i, st2.copy())
        nb.numba_bb_inc(a, 5, 2.0, i, st3.copy())
        nb.numba_macd_inc(a, 3, 5, 2, i, st4.copy())
        nb.numba_swma(a, i)
        nb.numba_dema_inc(a, 5, i, st3.copy(), raw)
        nb.numba_tema_inc(a, 5, i, st4.copy(), raw, raw2)
        nb.numba_hma_inc(a, 9, i, st7.copy(), raw)
        nb.numba_change(a, 1, i)
        nb.numba_nz(float(i), 0.0)
        nb.numba_crossover(a, l, i)
        nb.numba_crossunder(a, h, i)


def _warm_common_numba_builtins() -> None:
    """JIT-compile the hottest shared kernels once per process.

    Generated ``execute_script_compiled`` still JITs per IR, but first-touch
    cost of common ``*_inc`` kernels is paid only once when many distinct
    scripts share the same builtins.

    On corrupt Numba ``.nbi``/``.nbc`` (EOFError / UnpicklingError), purges
    known cache dirs and retries once so cold starts stay resilient.
    """
    global _BUILTINS_WARMED
    if _BUILTINS_WARMED or not _HAS_NUMBA:
        return
    _BUILTINS_WARMED = True
    try:
        _call_with_numba_cache_recovery(_run_common_numba_builtin_warm)
    except Exception as exc:
        # Warm-up is best-effort; real compile path surfaces real errors.
        # Do not leave _BUILTINS_WARMED False forever on transient failure —
        # avoid thrashing; next compile still warms via generated entry.
        _log.debug("numba builtin prewarm failed (best-effort): %s", exc, exc_info=True)


def prewarm_numba_builtins(*, force: bool = False) -> bool:
    """Public cold-start hook: JIT shared kernels before the first script.

    Soft-fails when Numba is missing (returns ``False``). Safe to call from
    Pro API startup, ``POST /compile/prewarm``, or ``pynescript prewarm``.

    Parameters
    ----------
    force:
        When true, re-run warm-up even if already completed this process.

    Returns
    -------
    bool
        ``True`` if Numba is available (warm-up attempted or already done),
        ``False`` if Numba is missing.
    """
    global _BUILTINS_WARMED
    if not _HAS_NUMBA:
        return False
    if force:
        _BUILTINS_WARMED = False
    ensure_compile_cache_dir()
    _warm_common_numba_builtins()
    return True


def prewarm_scripts(
    sources: list[str] | tuple[str, ...] | None = None,
    *,
    force_builtins: bool = False,
) -> dict[str, Any]:
    """Warm shared Numba builtins and optionally compile a list of Pine scripts.

    Used by operators and the Pro API prewarm endpoint to pay cold JIT cost
    before the first user request. Failures on individual scripts are recorded
    (correctness over speed — no silent empty result).

    Parameters
    ----------
    sources:
        Optional Pine source strings to :func:`compile_script` into the
        in-process + disk caches. ``None`` / empty → builtins only.
    force_builtins:
        Forwarded to :func:`prewarm_numba_builtins`.

    Returns
    -------
    dict
        ``has_numba``, ``builtins_warmed``, ``disk_cache_dir``,
        ``scripts_ok``, ``scripts_failed``, ``errors`` (list of short strings).
    """
    ensure_compile_cache_dir()
    numba_ok = prewarm_numba_builtins(force=force_builtins)
    ok = 0
    failed = 0
    errors: list[str] = []
    if sources:
        for i, src in enumerate(sources):
            if not isinstance(src, str) or not src.strip():
                failed += 1
                errors.append(f"scripts[{i}]: empty source")
                continue
            try:
                compile_script(src)
                ok += 1
            except Exception as exc:  # noqa: BLE001 — surface per-script; continue
                failed += 1
                msg = f"scripts[{i}]: {type(exc).__name__}: {exc}"
                if len(msg) > 240:
                    msg = msg[:237] + "..."
                errors.append(msg)
                _log.debug("prewarm_scripts failed for scripts[%s]: %s", i, exc, exc_info=True)
    stats = compile_cache_stats()
    return {
        "has_numba": numba_ok,
        "builtins_warmed": bool(stats.get("builtins_warmed")),
        "disk_cache_enabled": bool(stats.get("disk_cache_enabled")),
        "disk_cache_dir": stats.get("disk_cache_dir"),
        "source_entries": stats.get("source_entries"),
        "ir_entries": stats.get("ir_entries"),
        "scripts_ok": ok,
        "scripts_failed": failed,
        "errors": errors,
    }


def transpile(source: str) -> str:
    """Parse Pine source and return generated Python/Numba source string.

    Does **not** sanitize, exec, JIT, or cache. Useful for debugging the emitter.
    Empty visitor output raises :class:`CompileEmitError`.
    """
    tree = parse(source, mode="exec")
    visitor = CompilerVisitor()
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise CompileEmitError(msg)
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
    nopython_fallback_reason:
        When numeric warm-up failed with a Numba typing/nopython error and the
        engine re-emitted object mode, a short human-readable cause. ``None``
        when numeric mode succeeded or object mode was selected by the visitor.
    """

    source: str
    generated_code: str
    execute: Callable[..., Any]
    plot_titles: list[str] = field(default_factory=list)
    object_mode: bool = False
    nopython_fallback_reason: str | None = None

    def run(
        self,
        open_: np.ndarray | list[float],
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
        volume: np.ndarray | list[float] | None = None,
        time: np.ndarray | list[float] | None = None,
    ) -> dict[str, Any]:
        """Execute over full series; returns plots (+ optional ``__drawings`` / strategy).

        Coerces inputs to float64, defaults volume to ones, validates equal lengths,
        then :meth:`_pack_result` on the raw ``execute`` return value.

        *time* is bar-open Unix ms. When omitted, synthetic ``bar_index * 60_000``
        is used (unit-test / pure-compile default). Runtime hosts should pass
        real OHLCV timestamps for calendar/``timestamp``/``time[n]`` parity.
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
        if time is None:
            t = np.arange(n, dtype=np.float64) * 60000.0
        else:
            t = _as_f64(time)
            if len(t) != n:
                msg = "time array must have the same length as OHLCV"
                raise ValueError(msg)
        # Recover from truncated Numba .nbi/.nbc left after code edits / crashes.
        raw = _call_execute_with_recovery(self.execute, o, h, l, c, v, t)
        return self._pack_result(raw)

    def _pack_result(self, raw: Any) -> dict[str, Any]:
        """Map execute() output to the public plot-title dict.

        Numeric mode returns a tuple (or list) of plot arrays (avoids Numba
        typed.Dict). Object mode still returns a mapping (drawings / strategy
        extras).

        Series keys are **uniquified** like interpret Runtime packaging
        (``title``, ``title_2``, …) so duplicate ``plot(..., title=)`` strings
        do not silently drop earlier series (structural_only / false MISMATCH).
        """
        if _is_plot_sequence(raw):
            return _pack_plot_sequence(raw, self.plot_titles)
        return _normalize_result(raw)


def _call_execute_with_recovery(
    execute: Callable[..., Any],
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    v: np.ndarray,
    t: np.ndarray,
) -> Any:
    """Call ``execute_script_compiled`` with Numba cache + legacy arity recovery.

    Current IR is ``(open, high, low, close, volume, time)``. Disk modules from
    older engines may still be 5-arg (no ``time_arr``). On that TypeError, retry
    without *t* so stale disk IR still runs instead of hard-failing the host.
    """
    try:
        return _call_with_numba_cache_recovery(execute, o, h, l, c, v, t)
    except TypeError as exc:
        if not _is_legacy_execute_arity_error(exc):
            raise
        _log.debug(
            "execute arity mismatch (legacy 5-arg IR?); retrying without time_arr: %s",
            exc,
        )
        try:
            return _call_with_numba_cache_recovery(execute, o, h, l, c, v)
        except TypeError:
            raise exc from None


def _is_legacy_execute_arity_error(exc: BaseException) -> bool:
    """True when *exc* looks like 5-arg vs 6-arg ``execute_script_compiled``."""
    if not isinstance(exc, TypeError):
        return False
    msg = str(exc)
    # CPython: "takes 5 positional arguments but 6 were given"
    # Numba dispatcher wrappers may phrase differently.
    if "positional argument" in msg and ("5" in msg or "6" in msg):
        return True
    if "takes 5" in msg and "6" in msg:
        return True
    if "expected 5" in msg and "6" in msg:
        return True
    return False


def _is_plot_sequence(raw: Any) -> bool:
    """True when *raw* is a tuple/list of per-plot series (numeric emit shape).

    Distinguishes plot tuples from a bare list that is itself one series, and
    from mappings. Empty tuple/list counts as a (no-plot) sequence.
    """
    if isinstance(raw, tuple):
        return True
    if not isinstance(raw, list):
        return False
    if not raw:
        return True
    # List of arrays / array-likes from numeric emit (never a single series of
    # scalars — those come as ndarray or go through mapping normalize).
    first = raw[0]
    if isinstance(first, np.ndarray):
        return True
    # Nested sequence of equal-length samples is ambiguous; only treat as multi
    # plot when elements look like full series (list/tuple), not scalars.
    if isinstance(first, (list, tuple)):
        return True
    return False


def _uniquify_series_key(base: str, used: set[str]) -> str:
    """Return *base* or ``base_2`` / ``base_3`` … not already in *used*.

    Matches interpret Runtime packaging (``backend.runtime`` series_map loop).
    """
    key = base
    if key not in used:
        used.add(key)
        return key
    suffix = 2
    while True:
        candidate = f"{base}_{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def _pack_plot_sequence(
    raw: tuple[Any, ...] | list[Any],
    plot_titles: list[str] | None,
) -> dict[str, Any]:
    """Map a numeric-mode plot tuple/list onto uniquified title keys.

    Extra series beyond ``plot_titles`` get ``plot_{i}`` keys (never dropped).
    Missing series for trailing titles are omitted (partial return).
    """
    titles = list(plot_titles or [])
    out: dict[str, Any] = {}
    used: set[str] = set()
    n = len(raw)
    for i in range(n):
        if i < len(titles):
            base = titles[i]
            if base is None or (isinstance(base, str) and not str(base).strip()):
                base = f"plot_{i}"
            else:
                base = str(base)
        else:
            base = f"plot_{i}"
        key = _uniquify_series_key(base, used)
        out[key] = _coerce_plot_array(raw[i])
    return out


def _coerce_plot_array(v: Any) -> Any:
    """Ensure plot series are float64 arrays without redundant copies.

    ``None`` cells in Python lists become ``nan`` (interpret ``None`` parity for
    hosts that later JSON-null non-finites). Object arrays that cannot cast stay
    as-is (color/string columns) — never silent-coerce to zeros.
    """
    if v is None:
        # Single missing series → empty (caller should not pass None for a column)
        return np.asarray([], dtype=np.float64)
    if isinstance(v, np.ndarray):
        if v.dtype == np.float64:
            return v
        # Prefer float64 for numeric/object-with-None; keep non-castable dtypes.
        if v.dtype.kind in "biufc" or v.dtype == object:
            try:
                return v.astype(np.float64, copy=False)
            except (TypeError, ValueError):
                return v
        return v
    if isinstance(v, (list, tuple)):
        # Explicit path: None → nan without going through object→float pitfalls
        # on heterogeneous rows.
        try:
            out = np.empty(len(v), dtype=np.float64)
            for i, x in enumerate(v):
                if x is None:
                    out[i] = np.nan
                else:
                    try:
                        fx = float(x)
                        out[i] = fx
                    except (TypeError, ValueError):
                        # Fall back to asarray for exotic cells
                        return np.asarray(v, dtype=np.float64)
            return out
        except (TypeError, ValueError):
            pass
    try:
        return np.asarray(v, dtype=np.float64)
    except (TypeError, ValueError):
        return v


def _normalize_result(raw: Any) -> dict[str, Any]:
    """Convert numba typed dict / mapping / None into plain dict.

    Plot series become ``float64`` arrays. ``__drawings`` / ``__events``
    (object-mode) pass through as Python lists. Strategy scalars under ``__*``
    stay scalars; array-valued ``__*`` (e.g. equity series) are coerced.

    Bare sequences without :class:`CompiledScript` titles use ``plot_0``…
    (legacy / direct call). Does **not** invent zeros for missing plots.
    """
    if raw is None:
        return {}
    if _is_plot_sequence(raw):
        # Bare sequence without titles context — index keys
        return _pack_plot_sequence(raw, None)
    try:
        items = raw.items()
    except Exception:
        # Scalar / single array return — wrap under default key
        return {"plot": _coerce_plot_array(raw)}
    out: dict[str, Any] = {}
    used: set[str] = set()
    for k, v in items:
        key = str(k) if k is not None else "plot"
        if not key:
            key = "plot"
        if key in ("__drawings", "__events"):
            out[key] = list(v) if v is not None else []
            continue
        if key.startswith("__") and not isinstance(v, (list, tuple, np.ndarray)):
            # strategy scalars: __equity, __netprofit, __position_size
            out[key] = v
            continue
        # Guard against pathological duplicate keys from exotic mappings
        if key in out and not key.startswith("__"):
            key = _uniquify_series_key(key, used)
        else:
            used.add(key)
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
    # Importable numba exception types (when installed)
    if _HAS_NUMBA:
        try:
            from numba.core.errors import NumbaError as _NumbaError
            from numba.core.errors import TypingError as _TypingError

            if isinstance(exc, (_TypingError, _NumbaError)):
                return True
        except Exception:
            pass
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
        "Unknown attribute",
        "Invalid use of",
    )
    return any(m in msg for m in markers)


def _format_fallback_reason(exc: BaseException) -> str:
    """Short, user-facing reason for nopython → object-mode recovery."""
    name = type(exc).__name__
    msg = str(exc).strip().replace("\n", " ")
    if len(msg) > 240:
        msg = msg[:237] + "..."
    if msg:
        return f"nopython JIT failed ({name}): {msg}"
    return f"nopython JIT failed ({name})"


def _transpile_once(
    source: str,
    *,
    force_object_mode: bool = False,
) -> tuple[str, list[str], bool]:
    """Parse + emit. Returns ``(generated_code, plot_titles, object_mode)``."""
    try:
        tree = parse(source, mode="exec")
    except Exception as exc:
        # Surface parse failures as CompileError so auto-mode reasons stay typed.
        raise CompileEmitError(f"parse failed: {exc}") from exc
    visitor = CompilerVisitor(force_object_mode=force_object_mode)
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise CompileEmitError(msg)
    object_mode = bool(visitor.object_mode) or force_object_mode
    # Collect titles then uniquify so CompiledScript.plot_titles matches run()
    # keys (interpret-style ``title_2``). Numeric packing uses this list; object
    # emit still embeds visitor titles in the dict literal (Agent 03 handoff
    # if plot() does not call _unique_plot_title).
    raw_titles: list[str] = []
    for i, p in enumerate(visitor.plots):
        t = p.get("title", f"plot_{i}")
        if t is None or (isinstance(t, str) and not str(t).strip()):
            t = f"plot_{i}"
        else:
            t = str(t)
        raw_titles.append(t)
    titles = _uniquify_title_list(raw_titles)
    return code, titles, object_mode


def _uniquify_title_list(titles: list[str]) -> list[str]:
    """Stable uniquify of plot title list (``a``, ``a_2``, …)."""
    used: set[str] = set()
    out: list[str] = []
    for i, t in enumerate(titles):
        base = t if t else f"plot_{i}"
        out.append(_uniquify_series_key(str(base), used))
    return out


def _code_for_disk(code: str, *, object_mode: bool) -> str:
    """Rewrite njit decorator so Numba can cache machine code from a real file."""
    if object_mode or _NJIT_CACHE_FALSE not in code:
        return code
    return code.replace(_NJIT_CACHE_FALSE, _NJIT_CACHE_TRUE)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _disk_ir_path(ir_key: str) -> Path:
    return _disk_cache_dir() / f"ir_{ir_key[:40]}.py"


def _disk_src_meta_path(source_key: str) -> Path:
    return _disk_cache_dir() / f"src_{source_key[:40]}.json"


def _disk_write_artifacts(
    *,
    source_key: str,
    ir_key: str,
    code: str,
    titles: list[str],
    object_mode: bool,
    nopython_fallback_reason: str | None,
) -> None:
    if not _disk_cache_enabled():
        return
    try:
        disk_code = _code_for_disk(code, object_mode=object_mode)
        _write_text_atomic(_disk_ir_path(ir_key), disk_code)
        meta = {
            "v": _DISK_META_VERSION,
            "ir_key": ir_key,
            "titles": list(titles),
            "object_mode": bool(object_mode),
            "nopython_fallback_reason": nopython_fallback_reason,
        }
        _write_text_atomic(_disk_src_meta_path(source_key), json.dumps(meta, separators=(",", ":")))
    except OSError as exc:
        _log.debug("disk compile cache write failed: %s", exc)


def _import_disk_module(ir_key: str, code: str, *, object_mode: bool) -> Callable[..., Any] | None:
    """Load ``execute_script_compiled`` from a disk module (enables Numba file cache)."""
    if not _disk_cache_enabled():
        return None
    try:
        path = _disk_ir_path(ir_key)
        disk_code = _code_for_disk(code, object_mode=object_mode)
        if not path.is_file() or path.read_text(encoding="utf-8") != disk_code:
            _write_text_atomic(path, disk_code)
        mod_name = f"pynescript_compiled_{ir_key[:24]}"
        # Drop stale module so re-compile after IR change reloads.
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        fn = getattr(module, "execute_script_compiled", None)
        if fn is None or not callable(fn):
            return None
        return fn
    except Exception as exc:
        _log.debug("disk module import failed for %s: %s", ir_key[:12], exc, exc_info=True)
        return None


def _read_disk_src_meta(source_key: str) -> dict[str, Any] | None:
    """Load source→IR disk index JSON, or None if missing/invalid."""
    if not _disk_cache_enabled():
        return None
    meta_path = _disk_src_meta_path(source_key)
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if int(meta.get("v", 0)) != _DISK_META_VERSION:
            return None
        if not meta.get("ir_key"):
            return None
        return meta
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        _log.debug("disk src meta read failed: %s", exc)
        return None


def _try_load_disk_compiled(source: str, source_key: str) -> CompiledScript | None:
    """Rehydrate CompiledScript from disk source index + IR module (no re-parse)."""
    meta = _read_disk_src_meta(source_key)
    if meta is None:
        return None
    try:
        ir_key = str(meta["ir_key"])
        titles = list(meta.get("titles") or [])
        object_mode = bool(meta.get("object_mode"))
        reason = meta.get("nopython_fallback_reason")
        if reason is not None:
            reason = str(reason)
        ir_path = _disk_ir_path(ir_key)
        if not ir_path.is_file():
            return None
        code_disk = ir_path.read_text(encoding="utf-8")
        # Normalize to in-memory IR form (cache=False) for stable ir_key sharing.
        gen = code_disk.replace(_NJIT_CACHE_TRUE, _NJIT_CACHE_FALSE)
        # Prefer import path for Numba file-cache; fall back to exec.
        fn = _import_disk_module(ir_key, gen, object_mode=object_mode)
        if fn is None:
            if not object_mode and not _HAS_NUMBA:
                raise CompileNumbaRequiredError(
                    "numba is required for numeric compile mode (pip install numba)"
                )
            if not object_mode:
                _warm_common_numba_builtins()
            namespace: dict[str, Any] = {"__name__": "pynescript_compiled"}
            # Disk file may have cache=True — fine for exec if Numba accepts it.
            exec(code_disk, namespace)  # noqa: S102
            fn = namespace.get("execute_script_compiled")
            if fn is None or not callable(fn):
                return None
        return CompiledScript(
            source=source,
            generated_code=gen,
            execute=fn,
            plot_titles=titles,
            object_mode=object_mode,
            nopython_fallback_reason=reason,
        )
    except CompileError:
        raise
    except Exception as exc:
        _log.debug("disk compiled load failed: %s", exc, exc_info=True)
        return None


def _exec_generated(
    source: str,
    code: str,
    titles: list[str],
    object_mode: bool,
    *,
    ir_key: str | None = None,
    nopython_fallback_reason: str | None = None,
) -> CompiledScript:
    """Exec generated module text and bind ``execute_script_compiled``."""
    if not object_mode and not _HAS_NUMBA:
        msg = "numba is required for numeric compile mode (pip install numba)"
        raise CompileNumbaRequiredError(msg)

    if not object_mode:
        _warm_common_numba_builtins()

    fn: Callable[..., Any] | None = None
    if ir_key is not None:
        fn = _import_disk_module(ir_key, code, object_mode=object_mode)

    if fn is None:
        namespace: dict[str, Any] = {"__name__": "pynescript_compiled"}
        try:
            exec(code, namespace)  # noqa: S102 — intentional compile pipeline
        except Exception as exc:
            raise CompileLoadError(f"exec generated module failed: {exc}") from exc
        fn = namespace.get("execute_script_compiled")
        if fn is None or not callable(fn):
            msg = "generated code missing execute_script_compiled()"
            raise CompileLoadError(msg)

    return CompiledScript(
        source=source,
        generated_code=code,
        execute=fn,
        plot_titles=titles,
        object_mode=object_mode,
        nopython_fallback_reason=nopython_fallback_reason,
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
    ir_key = _sha256_text(code)
    return _exec_generated(source, code, titles, object_mode, ir_key=ir_key)


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
        nopython_fallback_reason=base.nopython_fallback_reason,
    )


def _sanitize_source(source: str) -> str:
    """Best-effort corpus sanitize; keep raw source if sanitize fails."""
    try:
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        return sanitize_corpus_source(source)
    except Exception as exc:
        _log.debug("sanitize_corpus_source failed (using raw): %s", exc)
        return source


def _memory_cache_get(key: str) -> CompiledScript | None:
    if key not in _COMPILE_CACHE:
        return None
    _COMPILE_CACHE.move_to_end(key)
    return _COMPILE_CACHE[key]


def _memory_cache_store(keys: list[str], compiled: CompiledScript) -> None:
    for key in keys:
        _cache_put(_COMPILE_CACHE, key, compiled, _COMPILE_CACHE_MAX)


def _warm_numeric_or_fallback(
    source: str,
    compiled: CompiledScript,
    *,
    ir_key: str,
) -> tuple[CompiledScript, str]:
    """Warm njit entry; on nopython failure re-emit object mode.

    Returns ``(compiled, ir_key)`` — *ir_key* may change after object re-emit.
    Never returns a known-broken nopython dispatcher: either warm succeeds,
    object-mode recovery succeeds, or a :class:`CompileError` is raised.
    """
    if compiled.object_mode:
        return compiled, ir_key

    dummy = np.arange(16, dtype=np.float64)
    dummy_t = dummy * 60000.0
    try:
        # First call may load Numba disk cache for nested numba_builtins;
        # recover from corrupt .nbi/.nbc instead of deferring EOFError to run.
        _call_with_numba_cache_recovery(
            compiled.execute, dummy, dummy, dummy, dummy, dummy, dummy_t
        )
        return compiled, ir_key
    except Exception as exc:
        if _is_numba_cache_corruption(exc):
            # Recovery already retried once inside _call_with_numba_cache_recovery.
            msg = f"Numba function cache load failed after purge: {exc}"
            raise CompileLoadError(msg) from exc
        if not _is_numba_nopython_failure(exc):
            # Defer non-typing failures to first real run (dummy OHLCV may be
            # unrepresentative). Do not invent results.
            _log.debug(
                "numeric warm-up non-nopython error (deferred to run): %s",
                exc,
                exc_info=True,
            )
            return compiled, ir_key

        reason = _format_fallback_reason(exc)
        _log.info("compile nopython → object mode: %s", reason)
        # Structural recovery: re-emit pure-Python object bar loop.
        try:
            code_o, titles_o, _ = _transpile_once(source, force_object_mode=True)
            ir_key_o = _sha256_text(code_o)
            recovered = _exec_generated(
                source,
                code_o,
                titles_o,
                True,
                ir_key=ir_key_o,
                nopython_fallback_reason=reason,
            )
        except CompileError:
            raise
        except Exception as rec_exc:
            raise CompileLoadError(
                f"nopython failed and object-mode recovery failed: {rec_exc} "
                f"(original: {reason})"
            ) from rec_exc
        return recovered, ir_key_o


def compile_script(source: str, *, use_cache: bool = True) -> CompiledScript:
    """Transpile Pine source and load the compiled entry point.

    Uses Numba when the script is pure-numeric; object-mode (UDT/map/drawing)
    uses a pure-Python numpy bar loop (still much faster than AST walking).

    If nopython JIT warm-up fails (pyobject arrays, unicode ops, …), re-emits
    the same script in object mode so ``mode=compile`` still runs, and sets
    :attr:`CompiledScript.nopython_fallback_reason`.

    Results are cached by source hash (max 128, LRU) so repeated
    ``Runtime.run(..., mode="compile")`` of the same script skips re-transpile
    and re-JIT warm-up. Raw source is probed **before** sanitize so warm hits
    skip sanitizer cost. A secondary IR cache (max 64) reuses an already-warm
    ``execute`` when two sources emit identical generated code (e.g. comment
    diffs). Optional disk cache (see module docstring) reuses modules / Numba
    file cache across process restarts.

    Scraped corpus sources are sanitized on cache miss (same as parse/runtime
    interpret) so docs chrome / Expand stubs do not fail compile-only paths.
    """
    raw_source = source
    raw_key = _sha256_text(raw_source)

    if use_cache:
        hit = _memory_cache_get(raw_key)
        if hit is not None:
            return hit

    source = _sanitize_source(raw_source)
    san_key = _sha256_text(source)
    cache_keys = [raw_key] if raw_key == san_key else [raw_key, san_key]

    if use_cache and san_key != raw_key:
        hit = _memory_cache_get(san_key)
        if hit is not None:
            # Alias raw → sanitized entry so next warm hit skips sanitize.
            _memory_cache_store([raw_key], hit)
            return hit

    # Disk source index (cross-process; still warms njit if Numba cache cold).
    # Prefer in-process IR share when the on-disk meta points at an IR we already
    # warmed — avoids a second CPUDispatcher for comment-only source variants.
    if use_cache:
        disk_meta = _read_disk_src_meta(san_key)
        if disk_meta is not None:
            ir_key_meta = str(disk_meta.get("ir_key") or "")
            if ir_key_meta and ir_key_meta in _IR_CACHE:
                compiled = _share_compiled(source, _IR_CACHE[ir_key_meta])
                _memory_cache_store(cache_keys, compiled)
                _IR_CACHE.move_to_end(ir_key_meta)
                # Ensure this source hash has a disk index entry too.
                _disk_write_artifacts(
                    source_key=san_key,
                    ir_key=ir_key_meta,
                    code=compiled.generated_code,
                    titles=compiled.plot_titles,
                    object_mode=compiled.object_mode,
                    nopython_fallback_reason=compiled.nopython_fallback_reason,
                )
                return compiled

        disk_hit = _try_load_disk_compiled(source, san_key)
        if disk_hit is not None:
            ir_key_d = _sha256_text(disk_hit.generated_code)
            # Another source may have already warmed this IR while we loaded
            # from disk (race-free in single-thread; still cheap to re-check).
            if ir_key_d in _IR_CACHE:
                disk_hit = _share_compiled(source, _IR_CACHE[ir_key_d])
            elif not disk_hit.object_mode:
                disk_hit, ir_key_d = _warm_numeric_or_fallback(
                    source, disk_hit, ir_key=ir_key_d
                )
            _memory_cache_store(cache_keys, disk_hit)
            _cache_put(_IR_CACHE, ir_key_d, disk_hit, _IR_CACHE_MAX)
            _disk_write_artifacts(
                source_key=san_key,
                ir_key=ir_key_d,
                code=disk_hit.generated_code,
                titles=disk_hit.plot_titles,
                object_mode=disk_hit.object_mode,
                nopython_fallback_reason=disk_hit.nopython_fallback_reason,
            )
            return disk_hit

    code, titles, object_mode = _transpile_once(source, force_object_mode=False)
    ir_key = _sha256_text(code)

    # Same generated IR as a prior script → reuse warm njit callable.
    if use_cache and ir_key in _IR_CACHE:
        compiled = _share_compiled(source, _IR_CACHE[ir_key])
        _memory_cache_store(cache_keys, compiled)
        _IR_CACHE.move_to_end(ir_key)
        _disk_write_artifacts(
            source_key=san_key,
            ir_key=ir_key,
            code=compiled.generated_code,
            titles=compiled.plot_titles,
            object_mode=compiled.object_mode,
            nopython_fallback_reason=compiled.nopython_fallback_reason,
        )
        return compiled

    compiled = _exec_generated(source, code, titles, object_mode, ir_key=ir_key)
    compiled, ir_key = _warm_numeric_or_fallback(source, compiled, ir_key=ir_key)

    if use_cache:
        _memory_cache_store(cache_keys, compiled)
        _cache_put(_IR_CACHE, ir_key, compiled, _IR_CACHE_MAX)
        _disk_write_artifacts(
            source_key=san_key,
            ir_key=ir_key,
            code=compiled.generated_code,
            titles=compiled.plot_titles,
            object_mode=compiled.object_mode,
            nopython_fallback_reason=compiled.nopython_fallback_reason,
        )
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
