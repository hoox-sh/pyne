#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interpret vs compile series parity harness.

Select N scripts from ``tests/data/builtin_scripts/*.pine`` (or ``--glob`` /
``--files``), run each with ``backend.runtime.Runtime`` in ``mode=interpret``
and ``mode=compile``, and compare ``result["series"]`` plot values with
nan-aware allclose (``rtol=1e-5``, ``atol=1e-6``).

Usage (from repo root)::

    python scripts/compare_interp_compile.py --bars 1000 --limit 50
    python scripts/compare_interp_compile.py --glob 'ta_*.pine' --bars 200
    python scripts/compare_interp_compile.py --files tests/data/builtin_scripts/average_true_range.pine
    python scripts/compare_interp_compile.py --ignore-hline-keys --ignore-fill-keys --strict-keys

Writes ``.cache/interp_compile_parity.json`` and prints summary buckets::

    OK, fill_background_only, both_error_same, expected_error, both_error,
    MISMATCH, interp_error, compile_error, structural_only

Exit code 0 when there are no value/nan mismatches among common series keys.
``both_error_same`` / ``expected_error`` (matched normalized errors on both
backends; latter = intentional auto-fib / pivot-depth demos) are treated as
success unless ``--strict-errors``. MISMATCH lines print
``interp=… compile=… n_bad=… max_abs=…`` detail. Structural key-only
differences warn by default; ``--strict-keys`` fails on leftover
only_interp/only_compile keys. ``--ignore-hline-keys`` / ``--ignore-fill-keys``
drop one-sided constant hline and Background/fill series from structural
residuals.

Caches (if compile looks wrong after editing numba_builtins / IR)
-----------------------------------------------------------------
Compile mode reuses:

- In-process LRU (cleared by process exit)
- Disk IR under ``$XDG_CACHE_HOME/pynescript/compile`` or
  ``~/.cache/pynescript/compile`` (``PYNE_COMPILE_CACHE_DIR`` override)
- Numba ``@njit(cache=True)`` ``.nbi``/``.nbc`` next to
  ``src/pynescript/compiler/__pycache__/`` and under the disk IR
  ``__pycache__/``

Corrupt Numba caches raise ``EOFError`` / ``UnpicklingError``; the engine
purges and recompiles automatically. To force a clean slate::

    from pynescript.compiler import (
        clear_compile_cache,
        clear_disk_compile_cache,
        clear_numba_function_caches,
    )
    clear_compile_cache()
    clear_disk_compile_cache()
    clear_numba_function_caches()
    # shell: rm -rf ~/.cache/pynescript/compile \\
    #   src/pynescript/compiler/__pycache__/numba_builtins*.nb*
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time

from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any


_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

DEFAULT_GLOB_DIR = _ROOT / "tests" / "data" / "builtin_scripts"
DEFAULT_REPORT = _ROOT / ".cache" / "interp_compile_parity.json"
DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-6

# Per-process bar cache (workers)
_BARS_CACHE: dict[int, list[dict[str, Any]]] = {}


def make_bars(n: int = 1000) -> list[dict[str, Any]]:
    """Synthetic OHLCV bars shared by interpret and compile runs.

    Mild drift + small zig-zag so most indicators compute, but not enough
    structure for pivot-heavy builtins (e.g. Auto Fib Extension/Retracement).
    Those scripts intentionally ``runtime.error`` when pivots are insufficient;
    both backends should surface the same structured error
    (``both_error_same`` when messages match after normalization).
    ZigZag-based scripts also need a registered ``TradingView/ZigZag`` library;
    without it, empty stubs yield the same insufficient-pivot error.
    """
    bars: list[dict[str, Any]] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _is_na(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        # numpy scalars
        if hasattr(v, "dtype") and hasattr(v, "item"):
            return bool(math.isnan(float(v)))
    except (TypeError, ValueError, OverflowError):
        return False
    return False


def _to_float_or_none(v: Any) -> float | None:
    """Convert a series cell to float, or None if non-numeric / NA."""
    if _is_na(v):
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def is_constant_hline(values: list[Any]) -> bool:
    """True if all non-NA values are equal (constant hline-style series)."""
    seen: float | None = None
    has_num = False
    for v in values:
        if _is_na(v):
            continue
        fv = _to_float_or_none(v)
        if fv is None:
            return False
        has_num = True
        if seen is None:
            seen = fv
        elif abs(fv - seen) > 1e-12:
            return False
    return has_num


# Keys / titles that are fill() / bgcolor / "Background" band series (structural noise).
_FILL_BG_KEY_RE = re.compile(
    r"(background|bgcolor|\bfill\b|fill\s*$|background\s*fill)",
    re.IGNORECASE,
)


def is_fill_background_key(key: str) -> bool:
    """True for Background / bgcolor / fill-style series titles."""
    k = (key or "").strip()
    if not k:
        return False
    kl = k.lower()
    if kl in {"background", "bgcolor", "fill", "bg"}:
        return True
    if kl.startswith("bgcolor") or kl.startswith("fill"):
        return True
    if "background" in kl:
        return True
    if "fill" in kl and ("background" in kl or "band" in kl or kl.endswith(" fill")):
        return True
    return bool(_FILL_BG_KEY_RE.search(k))


def normalize_error(err: Any) -> str:
    """Normalize backend error strings for cross-mode comparison.

    Strips interpret/compile prefixes (bar index, "Compiled Runtime Error")
    and ``RuntimeError:`` wrappers so shared failures (e.g. auto_fib Depth)
    compare equal.
    """
    if err is None:
        return ""
    s = str(err).replace("\n", " ").strip()
    if not s:
        return ""
    # Drop host prefixes repeatedly (order can vary slightly).
    # Bar timestamps may be int ms or float (e.g. 4234600000.0).
    for _ in range(4):
        prev = s
        s = re.sub(
            r"^Runtime Error at bar\s+[0-9]+(?:\.[0-9]+)?\s*\(index\s+[0-9]+\):\s*",
            "",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(r"^Compiled Runtime Error:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^Runtime Error:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^RuntimeError:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^Error:\s*", "", s, flags=re.IGNORECASE)
        s = s.strip()
        if s == prev:
            break
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def format_mismatch_detail(
    *,
    index: int,
    left: Any,
    right: Any,
    n_bad: int = 1,
    max_abs_diff: float | None = None,
    kind: str = "value",
) -> str:
    """Human-readable single-series mismatch line for reports / tests.

    Examples::

        index 2: interp=61.70 compile=na (type/na) n_bad=3
        index 0: interp=1.0 compile=1.001 abs_diff=1e-3 n_bad=12 max_abs=0.05
    """
    parts = [f"index {index}: interp={left!r} compile={right!r}"]
    if kind and kind != "value":
        parts.append(f"({kind})")
    if n_bad > 1:
        parts.append(f"n_bad={n_bad}")
    if max_abs_diff is not None and max_abs_diff == max_abs_diff:  # not NaN
        parts.append(f"max_abs={max_abs_diff:.6g}")
    return " ".join(parts)


def series_allclose(
    a: list[Any],
    b: list[Any],
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> tuple[bool, str]:
    """Nan-aware comparison of two plot value lists.

    ``None`` and NaN are treated as equal. Non-numeric pairs use equality.
    Mismatch details use ``interp=… compile=…`` labels plus ``n_bad`` /
    ``max_abs`` when more than one cell differs.
    """
    if len(a) != len(b):
        return False, f"length {len(a)} != {len(b)}"

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    if np is not None:
        aa = np.empty(len(a), dtype=np.float64)
        bb = np.empty(len(b), dtype=np.float64)
        type_bad: list[int] = []
        for i, (x, y) in enumerate(zip(a, b)):
            if _is_na(x) and _is_na(y):
                aa[i] = np.nan
                bb[i] = np.nan
                continue
            fx, fy = _to_float_or_none(x), _to_float_or_none(y)
            if fx is None and fy is None:
                if x != y:
                    return False, format_mismatch_detail(
                        index=i, left=x, right=y, kind="non-numeric"
                    )
                aa[i] = 0.0
                bb[i] = 0.0
                continue
            if fx is None or fy is None:
                type_bad.append(i)
                # Placeholder so allclose path still runs if we only report type
                aa[i] = np.nan
                bb[i] = 0.0 if fy is not None else np.nan
                if fx is not None:
                    aa[i] = fx
                    bb[i] = np.nan
                continue
            aa[i] = fx
            bb[i] = fy
        if type_bad:
            i0 = type_bad[0]
            return False, format_mismatch_detail(
                index=i0,
                left=a[i0],
                right=b[i0],
                n_bad=len(type_bad),
                kind="type/na",
            )
        if not np.allclose(aa, bb, rtol=rtol, atol=atol, equal_nan=True):
            close = np.isclose(aa, bb, rtol=rtol, atol=atol, equal_nan=True)
            bad = np.where(~close)[0]
            i0 = int(bad[0]) if len(bad) else 0
            n_bad = int(len(bad))
            # max abs among finite pairs only
            max_abs: float | None = None
            if n_bad:
                diffs = np.abs(aa[bad] - bb[bad])
                finite = diffs[np.isfinite(diffs)]
                if len(finite):
                    max_abs = float(np.max(finite))
            return False, format_mismatch_detail(
                index=i0,
                left=a[i0],
                right=b[i0],
                n_bad=n_bad,
                max_abs_diff=max_abs,
                kind="value",
            )
        return True, ""

    # Pure-Python fallback
    n_bad = 0
    first: tuple[int, Any, Any, str] | None = None
    max_abs = 0.0
    for i, (x, y) in enumerate(zip(a, b)):
        if _is_na(x) and _is_na(y):
            continue
        fx, fy = _to_float_or_none(x), _to_float_or_none(y)
        if fx is None and fy is None:
            if x != y:
                n_bad += 1
                if first is None:
                    first = (i, x, y, "non-numeric")
            continue
        if fx is None or fy is None:
            n_bad += 1
            if first is None:
                first = (i, x, y, "type/na")
            continue
        diff = abs(fx - fy)
        if diff > atol + rtol * abs(fy):
            n_bad += 1
            if diff > max_abs:
                max_abs = diff
            if first is None:
                first = (i, fx, fy, "value")
    if first is not None:
        i0, lv, rv, kind = first
        return False, format_mismatch_detail(
            index=i0,
            left=lv,
            right=rv,
            n_bad=n_bad,
            max_abs_diff=max_abs if kind == "value" and n_bad else None,
            kind=kind,
        )
    return True, ""


def compare_series_maps(
    interp: dict[str, list[Any]],
    compile_: dict[str, list[Any]],
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    ignore_hline_keys: bool = False,
    ignore_fill_keys: bool = False,
) -> dict[str, Any]:
    """Compare series dicts; return only_*/mismatches detail."""
    ki = set(interp.keys())
    kc = set(compile_.keys())
    only_interp = sorted(ki - kc)
    only_compile = sorted(kc - ki)
    common = sorted(ki & kc)

    ignored_hline: list[str] = []
    if ignore_hline_keys:
        kept_oi: list[str] = []
        for k in only_interp:
            if is_constant_hline(interp[k]):
                ignored_hline.append(k)
            else:
                kept_oi.append(k)
        only_interp = kept_oi
        kept_oc: list[str] = []
        for k in only_compile:
            if is_constant_hline(compile_[k]):
                ignored_hline.append(k)
            else:
                kept_oc.append(k)
        only_compile = kept_oc

    ignored_fill: list[str] = []
    if ignore_fill_keys:
        kept_oi = []
        for k in only_interp:
            if is_fill_background_key(k):
                ignored_fill.append(k)
            else:
                kept_oi.append(k)
        only_interp = kept_oi
        kept_oc = []
        for k in only_compile:
            if is_fill_background_key(k):
                ignored_fill.append(k)
            else:
                kept_oc.append(k)
        only_compile = kept_oc

    mismatches: list[dict[str, Any]] = []
    for k in common:
        ok, detail = series_allclose(interp[k], compile_[k], rtol=rtol, atol=atol)
        if not ok:
            mismatches.append({"key": k, "detail": detail})

    only_keys = only_interp + only_compile
    fill_background_only = bool(only_keys) and all(is_fill_background_key(k) for k in only_keys)

    return {
        "only_interp": only_interp,
        "only_compile": only_compile,
        "common_keys": common,
        "mismatches": mismatches,
        "ignored_hline_keys": ignored_hline,
        "ignored_fill_keys": ignored_fill,
        "fill_background_only": fill_background_only,
    }


def _err_str(err: Any) -> str:
    if err is None:
        return ""
    s = str(err).replace("\n", " ")
    return s[:300]


def run_one_script(
    path_str: str,
    n_bars: int,
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    ignore_hline_keys: bool = False,
    ignore_fill_keys: bool = False,
    sanitize: bool = True,
) -> dict[str, Any]:
    """Run one script interpret + compile and compare series.

    Safe to call from worker processes (re-adds sys.path).
    """
    root = str(_ROOT)
    src_root = str(_ROOT / "src")
    if root not in sys.path:
        sys.path.insert(0, root)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    path = Path(path_str)
    rel = path.name
    try:
        rel = str(path.resolve().relative_to(_ROOT))
    except ValueError:
        pass

    t0 = time.perf_counter()
    result: dict[str, Any] = {
        "file": rel,
        "path": str(path),
        "status": "OK",
        "only_interp": [],
        "only_compile": [],
        "mismatches": [],
        "ignored_hline_keys": [],
        "ignored_fill_keys": [],
        "fill_background_only": False,
        "interp_error": None,
        "compile_error": None,
        "normalized_interp_error": "",
        "normalized_compile_error": "",
        "ms_interp": 0,
        "ms_compile": 0,
        "ms_total": 0,
        "common_keys": [],
    }

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if sanitize:
            from pynescript.util.corpus_sanitize import sanitize_corpus_source

            src = sanitize_corpus_source(raw)
        else:
            src = raw
    except Exception as e:  # noqa: BLE001
        result["status"] = "interp_error"
        result["interp_error"] = f"read/sanitize: {type(e).__name__}: {e}"
        result["normalized_interp_error"] = normalize_error(result["interp_error"])
        result["ms_total"] = int((time.perf_counter() - t0) * 1000)
        return result

    if n_bars not in _BARS_CACHE:
        _BARS_CACHE[n_bars] = make_bars(n_bars)
    bars = _BARS_CACHE[n_bars]

    from backend.runtime import Runtime

    ti0 = time.perf_counter()
    try:
        ri = Runtime(symbol="PARITY").run(src, bars, mode="interpret")
    except Exception as e:  # noqa: BLE001
        ri = {"error": f"{type(e).__name__}: {e}", "series": {}}
    result["ms_interp"] = int((time.perf_counter() - ti0) * 1000)

    tc0 = time.perf_counter()
    try:
        rc = Runtime(symbol="PARITY").run(src, bars, mode="compile")
    except Exception as e:  # noqa: BLE001
        rc = {"error": f"{type(e).__name__}: {e}", "series": {}}
    result["ms_compile"] = int((time.perf_counter() - tc0) * 1000)

    ei = ri.get("error")
    ec = rc.get("error")
    if ei:
        result["interp_error"] = _err_str(ei)
    if ec:
        result["compile_error"] = _err_str(ec)
    result["normalized_interp_error"] = normalize_error(ei)
    result["normalized_compile_error"] = normalize_error(ec)

    if ei and ec:
        ni = result["normalized_interp_error"]
        nc = result["normalized_compile_error"]
        if ni and ni == nc:
            # Intentional runtime.error / pivot-depth demos → expected_error bucket
            # (still non-fatal; --strict-errors fails all error statuses).
            if is_expected_error_message(ni):
                result["status"] = "expected_error"
            else:
                result["status"] = "both_error_same"
        else:
            result["status"] = "both_error"
        result["ms_total"] = int((time.perf_counter() - t0) * 1000)
        return result
    if ei:
        result["status"] = "interp_error"
        result["ms_total"] = int((time.perf_counter() - t0) * 1000)
        return result
    if ec:
        result["status"] = "compile_error"
        result["ms_total"] = int((time.perf_counter() - t0) * 1000)
        return result

    si = ri.get("series") or {}
    sc = rc.get("series") or {}
    if not isinstance(si, dict):
        si = {}
    if not isinstance(sc, dict):
        sc = {}

    cmp_ = compare_series_maps(
        si,
        sc,
        rtol=rtol,
        atol=atol,
        ignore_hline_keys=ignore_hline_keys,
        ignore_fill_keys=ignore_fill_keys,
    )
    result.update(cmp_)
    if cmp_["mismatches"]:
        result["status"] = "MISMATCH"
    elif cmp_.get("fill_background_only") and (cmp_["only_interp"] or cmp_["only_compile"]):
        # Structural residual: only Background / fill keys on one side.
        result["status"] = "fill_background_only"
    else:
        result["status"] = "OK"
    result["ms_total"] = int((time.perf_counter() - t0) * 1000)
    return result


def _worker_job(payload: tuple[Any, ...]) -> dict[str, Any]:
    # payload: path, bars, rtol, atol, ignore_hline, sanitize [, ignore_fill]
    path_str, n_bars, rtol, atol, ignore_hline, sanitize = payload[:6]
    ignore_fill = bool(payload[6]) if len(payload) > 6 else False
    return run_one_script(
        path_str,
        n_bars,
        rtol=rtol,
        atol=atol,
        ignore_hline_keys=ignore_hline,
        ignore_fill_keys=ignore_fill,
        sanitize=sanitize,
    )


def _proc_target(payload: tuple[Any, ...], q: Any) -> None:
    """Module-level worker for spawn (must be picklable)."""
    try:
        q.put(_worker_job(payload))
    except Exception as e:  # noqa: BLE001
        q.put(
            {
                "file": payload[0],
                "status": "FAIL",
                "error": f"{type(e).__name__}: {e}",
                "mismatches": [],
            }
        )


def select_scripts(
    *,
    limit: int = 50,
    offset: int = 0,
    glob_pat: str | None = None,
    files: list[str] | None = None,
    file_list: Path | None = None,
    script_dir: Path | None = None,
) -> list[Path]:
    """Resolve script paths to compare.

    ``offset`` skips the first N alphabetically sorted scripts (after filtering
    by ``--glob`` / dir). When ``--files`` / ``--file-list`` is set, offset/limit
    still apply to the resolved file list in the order given.
    """
    if file_list is not None:
        list_path = Path(file_list)
        if not list_path.is_file():
            raise SystemExit(f"error: file list missing: {list_path}")
        files = [
            ln.strip()
            for ln in list_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]

    if files:
        out: list[Path] = []
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                p = (_ROOT / p).resolve() if not p.exists() else p.resolve()
            if p.is_file():
                out.append(p)
            else:
                print(f"warning: missing file {f}", flush=True)
        if offset > 0:
            out = out[offset:]
        if limit > 0:
            out = out[:limit]
        return out

    base = script_dir or DEFAULT_GLOB_DIR
    if not base.is_dir():
        raise SystemExit(f"error: script dir missing: {base}")

    if glob_pat:
        # Pattern relative to base (e.g. "a*.pine" or "sub/**/*.pine")
        paths = sorted(base.glob(glob_pat))
        if not paths:
            paths = sorted(base.rglob(glob_pat))
    else:
        paths = sorted(base.glob("*.pine"))

    paths = [p for p in paths if p.is_file() and p.suffix == ".pine"]
    if offset > 0:
        paths = paths[offset:]
    if limit > 0:
        paths = paths[:limit]
    return paths


def default_workers() -> int:
    try:
        cpu = os.cpu_count() or 1
    except Exception:  # noqa: BLE001
        cpu = 1
    return max(1, min(8, cpu))


# Intentional both-backend runtime.error demos (matched after normalize_error).
# Classified as ``expected_error`` so residual buckets stay honest without
# soft-suppressing the underlying RuntimeError.
_EXPECTED_ERROR_NEEDLES: tuple[str, ...] = (
    "not enough data to calculate auto fib",
    "not enough data to calculate auto fib extension",
    "not enough data to calculate auto fib retracement",
    "change the chart's timeframe to a lower one",
    "select a smaller calculation depth",
)


def is_expected_error_message(normalized: str) -> bool:
    """True when a normalized dual-backend error is an intentional demo/guard."""
    s = (normalized or "").strip().lower()
    if not s:
        return False
    return any(n in s for n in _EXPECTED_ERROR_NEEDLES)


# Primary status buckets printed in summary order.
_SUMMARY_BUCKET_ORDER = (
    "OK",
    "fill_background_only",
    "both_error_same",
    "expected_error",
    "both_error",
    "MISMATCH",
    "interp_error",
    "compile_error",
    "TIMEOUT",
    "FAIL",
    "structural_only",
)

# Statuses that do not fail the process by default (unless --strict-*).
_NON_FATAL_STATUSES = frozenset(
    {"OK", "fill_background_only", "both_error_same", "expected_error"}
)
_ERROR_STATUSES = frozenset(
    {
        "interp_error",
        "compile_error",
        "both_error",
        "both_error_same",
        "expected_error",
        "TIMEOUT",
        "FAIL",
    }
)


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    """Count status buckets; structural_only is derived (other key-only on OK)."""
    counts: dict[str, int] = {k: 0 for k in _SUMMARY_BUCKET_ORDER}
    for r in results:
        st = r.get("status") or "OK"
        if st in counts:
            counts[st] += 1
        else:
            counts[st] = counts.get(st, 0) + 1
        # Non-fill structural leftovers still reported under OK status.
        if st == "OK" and (r.get("only_interp") or r.get("only_compile")):
            counts["structural_only"] += 1
    return counts


def format_summary(counts: dict[str, int], *, total: int, elapsed_s: float) -> str:
    """Multi-line human-readable summary buckets."""
    lines = [f"Summary buckets ({total} scripts, elapsed_s={elapsed_s:.1f}):"]
    for key in _SUMMARY_BUCKET_ORDER:
        n = int(counts.get(key, 0))
        note = ""
        if key == "fill_background_only":
            note = "  # structural warn (Background/fill only)"
        elif key == "both_error_same":
            note = "  # matched errors (ok unless --strict-errors)"
        elif key == "expected_error":
            note = "  # intentional runtime.error / pivot demos (matched)"
        elif key == "both_error":
            note = "  # both backends failed, different messages"
        elif key == "structural_only":
            note = "  # other key-only diffs still on OK"
        elif key == "OK":
            note = "  # clean value parity"
        elif key == "MISMATCH":
            note = "  # value/nan mismatch (see detail: interp=… compile=…)"
        lines.append(f"  {key:22} {n}{note}")
    # Any unexpected statuses
    known = set(_SUMMARY_BUCKET_ORDER)
    for key, n in sorted(counts.items()):
        if key not in known and n:
            lines.append(f"  {key:22} {n}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Compare Runtime interpret vs compile series on corpus scripts.",
    )
    ap.add_argument("--bars", type=int, default=1000, help="OHLCV bar count (default 1000)")
    ap.add_argument("--limit", type=int, default=50, help="Max scripts to run (default 50; 0 = all)")
    ap.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N sorted scripts before applying --limit (default 0)",
    )
    ap.add_argument(
        "--glob",
        dest="glob_pat",
        default=None,
        help="Glob under tests/data/builtin_scripts (e.g. 'a*.pine')",
    )
    ap.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Explicit .pine paths (overrides --glob / default dir)",
    )
    ap.add_argument(
        "--file-list",
        type=Path,
        default=None,
        help="Path to a text file with one .pine path per line (avoids ARG_MAX)",
    )
    ap.add_argument(
        "--timeout-sec",
        type=float,
        default=90.0,
        help="Per-script wall timeout in seconds (default 90; 0 = no timeout)",
    )
    ap.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_GLOB_DIR,
        help=f"Script directory (default: {DEFAULT_GLOB_DIR})",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Process pool size (default min(8, cpu)={default_workers()})",
    )
    ap.add_argument("--rtol", type=float, default=DEFAULT_RTOL)
    ap.add_argument("--atol", type=float, default=DEFAULT_ATOL)
    ap.add_argument(
        "--ignore-hline-keys",
        action="store_true",
        default=False,
        help="Ignore constant hline-like series present on only one side",
    )
    ap.add_argument(
        "--ignore-fill-keys",
        action="store_true",
        default=False,
        help="Ignore Background/fill/bgcolor series present on only one side",
    )
    ap.add_argument(
        "--strict-keys",
        action="store_true",
        default=False,
        help="Exit non-zero when only_interp/only_compile keys remain",
    )
    ap.add_argument(
        "--strict-errors",
        action="store_true",
        default=False,
        help="Exit non-zero on any runtime error status (incl. both_error_same)",
    )
    ap.add_argument(
        "--no-sanitize",
        action="store_true",
        default=False,
        help="Skip corpus_sanitize on sources",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"JSON report path (default: {DEFAULT_REPORT})",
    )
    ap.add_argument(
        "--progress-every",
        type=int,
        default=5,
        help="Print progress every N completed scripts",
    )
    args = ap.parse_args(argv)

    workers = args.workers if args.workers is not None else default_workers()
    scripts = select_scripts(
        limit=args.limit,
        offset=args.offset,
        glob_pat=args.glob_pat,
        files=args.files,
        file_list=args.file_list,
        script_dir=args.dir,
    )
    if not scripts:
        print("error: no scripts selected", flush=True)
        return 2

    timeout_sec = float(args.timeout_sec or 0.0)
    print(
        f"interp/compile parity: {len(scripts)} scripts bars={args.bars} "
        f"workers={workers} timeout_sec={timeout_sec or 'none'} "
        f"rtol={args.rtol} atol={args.atol} "
        f"ignore_hline={args.ignore_hline_keys} ignore_fill={args.ignore_fill_keys} "
        f"strict_keys={args.strict_keys} strict_errors={args.strict_errors}",
        flush=True,
    )

    t_all = time.perf_counter()
    results: list[dict[str, Any]] = []
    payloads = [
        (
            str(p),
            args.bars,
            args.rtol,
            args.atol,
            args.ignore_hline_keys,
            not args.no_sanitize,
            args.ignore_fill_keys,
        )
        for p in scripts
    ]

    def _timeout_result(path_str: str, reason: str) -> dict[str, Any]:
        return {
            "file": path_str,
            "status": "TIMEOUT",
            "error": reason,
            "ms_total": int(timeout_sec * 1000) if timeout_sec else None,
            "mismatches": [],
        }

    if workers <= 1:
        for i, payload in enumerate(payloads, 1):
            r = _worker_job(payload)
            results.append(r)
            if i % max(1, args.progress_every) == 0 or i == len(payloads):
                print(
                    f"  [{i}/{len(payloads)}] {r.get('status'):22} {r.get('file')} "
                    f"({r.get('ms_total')}ms)",
                    flush=True,
                )
    else:
        # Explicit Process + join(timeout) so hung scripts are SIGTERM/SIGKILL'd.
        # ProcessPoolExecutor cannot reliably kill a stuck worker.
        ctx = mp.get_context("spawn")
        done = 0
        n_payloads = len(payloads)
        result_q: mp.Queue = ctx.Queue()
        timed_out_files: set[str] = set()

        def _record(r: dict[str, Any]) -> None:
            nonlocal done
            f = str(r.get("file") or "")
            if f in timed_out_files:
                return
            results.append(r)
            done += 1
            if done % max(1, args.progress_every) == 0 or done == n_payloads:
                print(
                    f"  [{done}/{n_payloads}] {r.get('status'):22} "
                    f"{r.get('file')} ({r.get('ms_total')}ms)",
                    flush=True,
                )

        def _drain_queue() -> None:
            while True:
                try:
                    r = result_q.get_nowait()
                except Exception:
                    break
                _record(r)

        idx = 0
        while idx < n_payloads:
            batch = payloads[idx : idx + workers]
            idx += len(batch)
            remaining: dict[int, tuple[mp.Process, str, float]] = {}
            for payload in batch:
                path_str = str(payload[0])
                p = ctx.Process(
                    target=_proc_target, args=(payload, result_q), daemon=True
                )
                p.start()
                remaining[id(p)] = (p, path_str, time.perf_counter())

            while remaining:
                now = time.perf_counter()
                for key in list(remaining.keys()):
                    p, path_str, t0 = remaining[key]
                    elapsed = now - t0
                    if p.is_alive() and timeout_sec > 0 and elapsed >= timeout_sec:
                        timed_out_files.add(path_str)
                        p.terminate()
                        p.join(timeout=2.0)
                        if p.is_alive():
                            p.kill()
                            p.join(timeout=1.0)
                        _record(
                            _timeout_result(
                                path_str,
                                f"exceeded per-script timeout ({timeout_sec}s)",
                            )
                        )
                        del remaining[key]
                    elif not p.is_alive():
                        p.join(timeout=0.5)
                        del remaining[key]
                _drain_queue()
                if remaining:
                    time.sleep(0.2)
            _drain_queue()

    # Stable order by file name
    results.sort(key=lambda r: str(r.get("file") or ""))
    counts = summarize(results)
    elapsed = time.perf_counter() - t_all

    report = {
        "bars": args.bars,
        "limit": args.limit,
        "offset": args.offset,
        "workers": workers,
        "rtol": args.rtol,
        "atol": args.atol,
        "ignore_hline_keys": args.ignore_hline_keys,
        "ignore_fill_keys": args.ignore_fill_keys,
        "strict_keys": args.strict_keys,
        "strict_errors": args.strict_errors,
        "elapsed_s": round(elapsed, 3),
        "counts": counts,
        "results": results,
    }
    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    n = len(results)
    print(f"\n{format_summary(counts, total=n, elapsed_s=elapsed)}", flush=True)
    print(f"Report: {out_path}", flush=True)

    # Sample residuals by bucket
    mism = [r for r in results if r.get("status") == "MISMATCH"]
    if mism:
        print("\nValue mismatches (first 10, with series detail):", flush=True)
        for r in mism[:10]:
            mm = r.get("mismatches") or []
            print(f"  {r.get('file')}: {len(mm)} series", flush=True)
            for m in mm[:4]:
                print(
                    f"    key={m.get('key')!r}  {m.get('detail')}",
                    flush=True,
                )
            if len(mm) > 4:
                print(f"    … +{len(mm) - 4} more series", flush=True)

    fill_only = [r for r in results if r.get("status") == "fill_background_only"]
    if fill_only:
        print("\nFill/background-only structural (first 10):", flush=True)
        for r in fill_only[:10]:
            print(
                f"  {r.get('file')}: only_interp={r.get('only_interp')[:5]} "
                f"only_compile={r.get('only_compile')[:5]}",
                flush=True,
            )

    structural = [
        r
        for r in results
        if r.get("status") == "OK" and (r.get("only_interp") or r.get("only_compile"))
    ]
    if structural:
        print("\nOther structural key diffs (warning, first 10):", flush=True)
        for r in structural[:10]:
            print(
                f"  {r.get('file')}: only_interp={r.get('only_interp')[:5]} "
                f"only_compile={r.get('only_compile')[:5]}",
                flush=True,
            )

    same_err = [r for r in results if r.get("status") == "both_error_same"]
    if same_err:
        print("\nBoth-error-same (matched normalized errors, first 10):", flush=True)
        for r in same_err[:10]:
            print(
                f"  {r.get('file')}: {r.get('normalized_interp_error', '')[:120]}",
                flush=True,
            )

    expected_err = [r for r in results if r.get("status") == "expected_error"]
    if expected_err:
        print("\nExpected-error (intentional demos, first 10):", flush=True)
        for r in expected_err[:10]:
            print(
                f"  {r.get('file')}: {r.get('normalized_interp_error', '')[:120]}",
                flush=True,
            )

    value_fail = counts.get("MISMATCH", 0) > 0
    key_fail = False
    if args.strict_keys:
        # Fail on leftover only_interp / only_compile after optional filters
        key_fail = any(
            (r.get("only_interp") or r.get("only_compile"))
            for r in results
            if r.get("status") in ("OK", "MISMATCH", "fill_background_only")
        )

    error_fail = False
    if args.strict_errors:
        error_fail = any((r.get("status") or "") in _ERROR_STATUSES for r in results)

    if value_fail or key_fail or error_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
