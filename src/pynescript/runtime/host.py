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

"""Pine Script runtime host (bar-loop) for Pro API and library callers.

:class:`Runtime` walks OHLCV bars in interpret mode (AST evaluator) or runs
the Numba/object compile pipeline. Host context includes ``syminfo``,
``timeframe``, ``barstate``, ``chart``, and lazy UTC calendar fields. Used by
``POST /run`` and CLI/showcase tools that need the same host semantics.

**Public import path:** :mod:`pynescript.runtime` (this module is the
implementation). ``backend.runtime`` re-exports the same symbols for
backward compatibility.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
import uuid
from sys import intern
from typing import Any

from pynescript.ast.helper import parse, walk
from pynescript.util.time_parts import utc_parts_from_ms

from .evaluator import CustomEvaluator
from .series import (
    make_pine_series,
    parse_max_bars_back_from_source,
    pineseries_history_length,
    resolve_series_cap,
    series_cap_enabled,
    series_cap_limit,
    series_ring_enabled,
    trim_series_lists,
)

# Bare calendar series keys (Pine time components written into host context).
_CAL_KEYS: tuple[str, ...] = (
    "year",
    "month",
    "dayofmonth",
    "hour",
    "minute",
    "second",
    "dayofweek",
)
_CAL_KEY_SET: frozenset[str] = frozenset(_CAL_KEYS)

# fill() needs plot() to return Plot handles (PlotRegistry).
_FILL_CALL_RE = re.compile(r"\bfill\s*\(")


def _env_truthy(name: str, default: bool = False) -> bool:
    """Parse common truthy env strings (``1``/``true``/``yes``/``on``)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class LazyCalendarContext(dict):
    """Host context that materializes UTC calendar fields on first read.

    Phase 1.4 — bar loop only records bar open time via :meth:`set_bar_time`.
    ``year`` / ``month`` / ``dayofmonth`` / ``hour`` / ``minute`` / ``second`` /
    ``dayofweek`` are filled with :func:`utc_parts_from_ms` the first time any
    of those keys is accessed on the bar.

    Scripts that never read calendar series (including false-positive name
    hits such as ``dayofweek.monday`` enum constants) pay near-zero calendar
    cost. Scripts that read them keep the integer-math path (no per-access
    ``datetime``).
    """

    __slots__ = ("_cal_ms", "_cal_filled")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cal_ms: int | float | None = None
        self._cal_filled: bool = False

    def set_bar_time(self, ms: int | float) -> None:
        """Advance bar open time; drop prior-bar calendar cache if materialised."""
        if self._cal_filled:
            dpop = dict.pop
            for k in _CAL_KEYS:
                dpop(self, k, None)
            self._cal_filled = False
        self._cal_ms = ms

    def _materialize(self) -> None:
        if self._cal_filled:
            return
        ms = self._cal_ms
        if ms is None:
            ms = 0
        try:
            parts = utc_parts_from_ms(ms)
        except (ValueError, OverflowError, TypeError):
            self._cal_filled = True
            return
        # Fill only missing keys so explicit user assignments survive.
        dset = dict.__setitem__
        dhas = dict.__contains__
        for name in _CAL_KEYS:
            if not dhas(self, name):
                dset(self, name, getattr(parts, name))
        self._cal_filled = True

    def __getitem__(self, key: Any) -> Any:  # type: ignore[override]
        if key in _CAL_KEY_SET and not self._cal_filled:
            # Honour explicit user assignment without forcing civil-date math.
            if dict.__contains__(self, key):
                return dict.__getitem__(self, key)
            self._materialize()
            return dict.__getitem__(self, key)
        return dict.__getitem__(self, key)

    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        if key in _CAL_KEY_SET:
            try:
                return self[key]
            except KeyError:
                return default
        return dict.get(self, key, default)


# Derived built-in series — skip update/append when script never names them.
_HL2_RE = re.compile(r"\bhl2\b")
_HLC3_RE = re.compile(r"\bhlc3\b")
_OHLC4_RE = re.compile(r"\bohlc4\b")
_TR_RE = re.compile(r"\btr\b")
_TIME_CLOSE_RE = re.compile(r"\btime_close\b")
# ta.vwap() / vwap with no source defaults to hlc3 (name may be absent).
_VWAP_RE = re.compile(r"\b(?:ta\.)?vwap\b")
# input.source dropdown can pick hl2/hlc3/ohlc4/tr even when those ids are absent.
_INPUT_SOURCE_RE = re.compile(r"\binput\.source\b")
# Strategy snapshot / drain only when the script actually uses the broker.
_STRATEGY_NAME_RE = re.compile(r"\bstrategy\b")
# Post-loop alert export — skip import when source has no alert() / alertcondition().
_ALERT_CALL_RE = re.compile(r"\balert(?:condition)?\s*\(")

# Parse trees: process-level LRU lives in ``pynescript.ast.helper.parse``
# (sha256(source)+mode, PYNE_PARSE_CACHE / PYNE_PARSE_CACHE_MAX). Host keeps
# a thin _parse_script wrapper for call-site clarity.

# Host-side compile cache (raw source sha256 → CompiledScript). Avoids re-running
# corpus sanitize + engine cache lookup on every mode=compile warm re-eval.
# Engine still has its own LRU; this is a thin SoT host short-circuit.
_HOST_COMPILE_CACHE: dict[str, Any] = {}
_HOST_COMPILE_CACHE_MAX = 64

# Auto-mode negative cache: source sha256 → compile failure reason. Skips re-transpile
# after a deterministic compile-time failure (not data-dependent runtime errors).
_HOST_COMPILE_FAIL_CACHE: dict[str, str] = {}
_HOST_COMPILE_FAIL_CACHE_MAX = 128

# Compiler package availability for mode=auto prefilter (None = not probed yet).
# Numba is NOT required for eligibility — object-mode compile is pure-Python.
_HAS_COMPILER: bool | None = None

# Structured Runtime error kinds (surfaced as ``error_kind`` on failure payloads).
# API always keeps the legacy string ``error`` field for backward compatibility.
ERROR_KIND_PARSE = "parse"
ERROR_KIND_COMPILE = "compile"
ERROR_KIND_RUNTIME = "runtime"
ERROR_KIND_DATA = "data"
ERROR_KIND_ORDER = "order"
ERROR_KIND_MODE = "mode"


def _error_payload(
    message: str,
    *,
    kind: str,
    exc: BaseException | None = None,
    bar_index: int | None = None,
    bar_time: Any = None,
) -> dict[str, Any]:
    """Build a classified Runtime error dict (fail-closed host contract).

    Always includes ``error`` (human message). Adds ``error_kind`` and optional
    ``error_type`` / ``error_bar`` / ``error_bar_time`` for hosts and tests.
    """
    body: dict[str, Any] = {
        "error": message,
        "error_kind": kind,
    }
    if exc is not None:
        body["error_type"] = type(exc).__name__
    if bar_index is not None:
        body["error_bar"] = int(bar_index)
    if bar_time is not None:
        body["error_bar_time"] = bar_time
    return body


def _format_exc_message(prefix: str, exc: BaseException) -> str:
    """``Prefix: TypeName: detail`` (omit redundant type when message already names it)."""
    et = type(exc).__name__
    detail = str(exc).strip() or et
    # Avoid "TypeError: TypeError: …" when str(exc) is empty-ish
    if detail == et:
        return f"{prefix}: {et}"
    return f"{prefix}: {et}: {detail}"


def _clear_pine_logger() -> None:
    """Reset the global Pine ``log.*`` buffer so runs do not leak messages."""
    try:
        from pynescript.ast.evaluator.builtins.logging import get_logger

        get_logger().clear()
    except Exception:  # noqa: BLE001 — logging is optional host plumbing
        pass


def _export_pine_logs() -> list[dict[str, str]]:
    """Export Pine ``log.*`` messages as JSON-safe ``{level, message}`` dicts."""
    try:
        from pynescript.ast.evaluator.builtins.logging import get_logger

        return [{"level": str(level).lower(), "message": str(message)} for level, message in get_logger().get_logs()]
    except Exception:  # noqa: BLE001
        return []


def _export_line_profile(evaluator: Any) -> list[dict[str, Any]]:
    """Convert evaluator ``_pine_line_profile`` map into AXIS gutter rows."""
    raw = getattr(evaluator, "_pine_line_profile", None)
    if not isinstance(raw, dict) or not raw:
        return []
    total = 0.0
    for v in raw.values():
        try:
            total += float(v[0])
        except (TypeError, ValueError, IndexError):
            pass
    denom = total if total > 0 else 1.0
    lines: list[dict[str, Any]] = []
    for ln, bucket in sorted(raw.items(), key=lambda kv: int(kv[0])):
        try:
            line_no = int(ln)
            ms = float(bucket[0])
            execs = int(bucket[1])
        except (TypeError, ValueError, IndexError):
            continue
        if line_no < 1:
            continue
        lines.append(
            {
                "line": line_no,
                "ms": round(ms, 3),
                "execs": execs,
                "pct": round((ms / denom) * 100.0, 2),
            }
        )
    return lines


def _build_run_profile(
    *,
    total_ms: float,
    bars: int,
    mode: str,
    parse_ms: float = 0.0,
    eval_ms: float = 0.0,
    lines: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Phase timings (+ optional per-line cost when profiler is on)."""
    return {
        "total_ms": round(float(total_ms), 3),
        "bars": int(bars),
        "mode": mode,
        "phases": {
            "parse_ms": round(float(parse_ms), 3),
            "eval_ms": round(float(eval_ms), 3),
        },
        "lines": list(lines or []),
    }


def _attach_logs_profile(
    result: dict[str, Any],
    *,
    total_ms: float,
    bars: int,
    mode: str,
    parse_ms: float = 0.0,
    eval_ms: float = 0.0,
    lines: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach top-level and ``meta`` ``logs`` / ``profile`` fields to a result dict."""
    logs = _export_pine_logs()
    profile = _build_run_profile(
        total_ms=total_ms,
        bars=bars,
        mode=mode,
        parse_ms=parse_ms,
        eval_ms=eval_ms,
        lines=lines,
    )
    result["logs"] = logs
    result["profile"] = profile
    meta = result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        result["meta"] = meta
    meta["logs"] = logs
    meta["profile"] = profile
    return result


def _json_safe_number(x: Any) -> float | None:
    """Map NaN/±Inf (and numpy scalars) to ``None`` for strict JSON / browsers."""
    if x is None:
        return None
    try:
        # numpy scalar → python
        if hasattr(x, "item") and not isinstance(x, (bytes, str, dict, list)):
            x = x.item()
    except Exception:  # noqa: BLE001
        pass
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        fx = float(x)
        if math.isnan(fx) or math.isinf(fx):
            return None
        return fx
    return None


def _color_str(c: Any) -> str | None:
    """JSON-safe color for plot_meta / bgcolor cells."""
    if c is None:
        return None
    t = type(c)
    if t is str:
        return c if c else None
    if t is int:
        return f"#{c & 0xFFFFFF:06X}"
    to_rgba = getattr(c, "to_rgba", None)
    if callable(to_rgba):
        try:
            return str(to_rgba())
        except Exception:
            pass
    to_hex = getattr(c, "to_hex", None)
    if callable(to_hex):
        try:
            return str(to_hex())
        except Exception:
            pass
    s = str(c)
    return s if s else None


def _json_plot_value(v: Any, kind: str) -> Any:
    """JSON-safe series cell for plot / bgcolor / plotshape kinds."""
    if v is None:
        return None
    # Unresolved library imports use a chainable stub whose ``__getattr__``
    # returns self — so ``hasattr(stub, "to_rgba")`` is True and would
    # otherwise serialize as ``"<PineImportStub …>"`` via ``_color_str``.
    if getattr(v, "__pine_import_stub__", False):
        return None
    t = type(v)
    if kind == "bgcolor":
        if t is str:
            return v if v else None
        return _color_str(v)
    if kind in ("plotshape", "plotchar"):
        if t is bool:
            return True if v else None
        if t is int or t is float:
            try:
                fv = float(v)
                if fv != fv:  # NaN
                    return None
                return True if fv != 0.0 else None
            except (TypeError, ValueError):
                return True if v else None
        return True if v else None
    if kind == "plotarrow":
        if t is bool:
            return float(v)
        if t is int or t is float:
            try:
                fv = float(v)
                return None if fv != fv else v
            except (TypeError, ValueError):
                return None
        return None
    # line / hline numeric. Non-numeric strings (library import stubs,
    # unresolved symbols) must not appear as plot series cells — AXIS
    # and interpret/compile parity treat them as ``na`` (null).
    if t is float or t is int:
        try:
            fv = float(v)
            return None if fv != fv else v
        except (TypeError, ValueError):
            return None
    if t is bool:
        return float(v)
    if t is str:
        s = v.strip()
        if not s or s.startswith("<PineImportStub") or s.startswith("<"):
            return None
        try:
            fv = float(s)
            return None if fv != fv else fv
        except (TypeError, ValueError):
            return None
    to_rgba = getattr(type(v), "to_rgba", None)
    to_hex = getattr(type(v), "to_hex", None)
    if callable(to_rgba) or callable(to_hex):
        return _color_str(v)
    return None


# Capture already stores JSON-safe cells for these kinds (fill series is all-null).
_PACK_READY_KINDS: frozenset[str] = frozenset(
    {
        "plot",
        "hline",
        "bgcolor",
        "barcolor",
        "fill",
        "plotshape",
        "plotchar",
        "plotarrow",
        "plotbar",
        "plotcandle",
    }
)


def _hline_fill_constant(values: list[Any]) -> list[Any]:
    """Fill hline None gaps with the first known price (in-place when possible)."""
    fill = None
    has_none = False
    for v in values:
        if v is None:
            has_none = True
        elif fill is None:
            fill = v
        if fill is not None and has_none:
            break
    if fill is None or not has_none:
        return values
    for i, v in enumerate(values):
        if v is None:
            values[i] = fill
    return values


def _pack_interpret_plot_columns(
    value_cols: list[list[Any]],
    meta_list: list[dict[str, Any]],
    *,
    bars_done: int = 0,
    pack_dirty: bool = False,
) -> tuple[dict[str, list[Any]], dict[str, dict[str, Any]], list[Any]]:
    """Build ``series`` / ``plot_meta`` / primary ``plots`` from columnar capture.

    Capture already stores JSON-safe cells for common kinds; reuse those lists
    (no per-cell scan / ``list()`` copy) unless ``pack_dirty`` or the kind is
    unknown. Incomplete runs (timeout) slice pre-sized columns to *bars_done*.
    """
    series_map: dict[str, list[Any]] = {}
    plot_meta: dict[str, dict[str, Any]] = {}
    max_plots = len(value_cols)
    if max_plots == 0:
        return series_map, plot_meta, []

    for pi in range(max_plots):
        m0 = meta_list[pi] if pi < len(meta_list) else {}
        if m0.get("ohlc_component"):
            continue  # consumed by its parent candle/bar entry
        # Capture meta titles are already str (or missing). Avoid str() + intern
        # churn when the same interned title is reused across warm re-runs.
        raw_title = m0.get("title")
        if raw_title is None or raw_title == "":
            title = f"plot_{pi}"
        elif type(raw_title) is str:
            title = raw_title
        else:
            title = str(raw_title)
        color = m0.get("color")
        if color is not None and type(color) is not str:
            color = _color_str(color)
        elif color == "":
            color = None
        linewidth = int(m0.get("linewidth") or 1)
        kind_raw = m0.get("kind") or m0.get("type") or "plot"
        kind = kind_raw if type(kind_raw) is str else str(kind_raw)
        style = m0.get("style")
        if style is not None:
            style = style if type(style) is str else str(style)
            if style == "":
                style = None
        linestyle = m0.get("linestyle")
        if linestyle is not None and type(linestyle) is not str:
            linestyle = str(linestyle)
        location = m0.get("location")
        if location is not None:
            location = location if type(location) is str else str(location)
            if location == "":
                location = None
        text = m0.get("text")
        if text is not None:
            text = text if type(text) is str else str(text)
            if text == "":
                text = None
        char = m0.get("char")
        if char is not None:
            char = char if type(char) is str else str(char)
            if char == "":
                char = None

        if title in series_map:
            base = title
            suffix = 2
            title = f"{base}_{suffix}"
            while title in series_map:
                suffix += 1
                title = f"{base}_{suffix}"
        if type(title) is str:
            title = intern(title)

        raw_col = value_cols[pi]
        n = bars_done if bars_done > 0 else len(raw_col)
        if n < len(raw_col):
            raw_col = raw_col[:n]
        # Reuse capture lists when cells are already JSON-safe.
        if kind in _PACK_READY_KINDS and not (pack_dirty and kind in ("plot", "hline")):
            values = raw_col
        else:
            values = [_json_plot_value(v, kind) for v in raw_col]
        if kind == "hline":
            values = _hline_fill_constant(values)
        series_map[title] = values
        meta_entry: dict[str, Any] = {
            "title": title,
            "color": color,
            "linewidth": linewidth,
            "index": pi,
            "kind": kind,
        }
        if style is not None:
            meta_entry["style"] = style
        if linestyle is not None:
            meta_entry["linestyle"] = linestyle
        if location is not None:
            meta_entry["location"] = location
        if text is not None:
            meta_entry["text"] = text
        if char is not None:
            meta_entry["char"] = char
        size = m0.get("size", m0.get("text_size"))
        if size is not None and size != "":
            meta_entry["size"] = size
            meta_entry["text_size"] = size
        if kind == "fill":
            for ref_key in ("plot1", "plot2"):
                ref = m0.get(ref_key)
                if ref is not None and str(ref).strip() != "":
                    meta_entry[ref_key] = str(ref)
        if kind == "hline":
            price_val = next((v for v in values if v is not None), None)
            if price_val is not None:
                try:
                    meta_entry["price"] = float(price_val)
                except (TypeError, ValueError):
                    meta_entry["price"] = price_val
        display = m0.get("display")
        if display is not None and display != "":
            meta_entry["display"] = display
        for key in ("offset", "show_last"):
            wv = m0.get(key)
            if isinstance(wv, (int, float)) and not isinstance(wv, bool):
                meta_entry[key] = int(wv)
        for key in ("trackprice", "join", "editable"):
            wv = m0.get(key)
            if isinstance(wv, bool):
                meta_entry[key] = wv
        wv = m0.get("histbase")
        if isinstance(wv, (int, float)) and not isinstance(wv, bool):
            try:
                meta_entry["histbase"] = float(wv)
            except (TypeError, ValueError):
                pass
        if kind in ("plotcandle", "plotbar"):
            for cparam in ("wickcolor", "bordercolor"):
                cv = m0.get(cparam)
                if isinstance(cv, str) and cv:
                    meta_entry[cparam] = cv
            meta_entry["close"] = title
            for off, ckey in ((1, "open"), (2, "high"), (3, "low")):
                cj = pi + off
                if cj >= max_plots:
                    break
                cm = meta_list[cj] if cj < len(meta_list) else {}
                if not cm.get("ohlc_component"):
                    break
                raw_c = value_cols[cj]
                cn = bars_done if bars_done > 0 else len(raw_c)
                if cn < len(raw_c):
                    raw_c = raw_c[:cn]
                cname = f"{title}.{ckey}"
                series_map[cname] = [_json_plot_value(v, "plot") for v in raw_c]
                meta_entry[ckey] = cname
        plot_meta[title] = meta_entry

    final_series = next(iter(series_map.values()), [])
    return series_map, plot_meta, final_series


def _series_values_jsonable(values: Any) -> list[Any]:
    """Convert a plot series (list / numpy) to JSON-safe list of floats|null.

    Hot path for ``mode=compile`` host wrap: numpy float64 arrays from
    ``CompiledScript.run``. Prefer C-level ``tolist()`` then sparse None fix
    for non-finite samples (warm-up ``na``) — much faster than per-element
    ``math.isnan`` / ``math.isinf`` in pure Python.
    """
    if values is None:
        return []
    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(values, np.ndarray):
            kind = values.dtype.kind
            if kind in "f":
                arr = np.asarray(values, dtype=np.float64).ravel()
                n = int(arr.size)
                if n == 0:
                    return []
                finite = np.isfinite(arr)
                if bool(finite.all()):
                    return arr.tolist()
                # tolist keeps nan/inf as float; patch only non-finite slots
                out: list[Any] = arr.tolist()
                # Sparse bad indices (warm-up head) vs dense: both beat pure-Python loop
                bad = np.flatnonzero(~finite)
                for i in bad:
                    out[int(i)] = None
                return out
            if kind in "iu":
                # Integers are always finite → direct list of floats for JSON
                return np.asarray(values, dtype=np.float64).ravel().tolist()
            if kind == "b":
                return [bool(x) for x in values.ravel()]
            # object / other: fall through via tolist
            values = values.tolist()
    except Exception:
        pass
    if hasattr(values, "tolist") and not isinstance(values, (list, tuple)):
        try:
            values = values.tolist()
        except Exception:
            return []
    if not isinstance(values, (list, tuple)):
        return []
    out_list: list[Any] = []
    append = out_list.append
    for x in values:
        if x is None:
            append(None)
        elif isinstance(x, bool):
            append(x)
        elif isinstance(x, (int, float)):
            fx = float(x)
            if math.isnan(fx) or math.isinf(fx):
                append(None)
            else:
                append(fx)
        elif hasattr(x, "item") and not isinstance(x, (str, bytes)):
            append(_json_safe_number(x))
        else:
            # Keep non-numeric as-is only if already JSON-friendly
            append(x if isinstance(x, (str, dict, list)) else None)
    return out_list


# Pack cache for warm re-runs of the same bar list (bench / re-eval).
# Keyed by id(list); entry stores (list identity, cheap fingerprint, packed).
# Fingerprint = (n, first.time, last.time, first.close, last.close) so in-place
# mutation of ends invalidates; full middle edits still rare for this host path.
# Packed tuple: (open, high, low, close, volume, time) as float64 arrays.
_OHLCV_PACK_CACHE: dict[int, tuple[Any, tuple, tuple[Any, Any, Any, Any, Any, Any]]] = {}
_OHLCV_PACK_CACHE_MAX = 8
# Parallel cache of Python float lists for interpret (same identity + fingerprint).
# Compile path asarrays from this so a warm interpret+compile pair packs once.
_OHLCV_LIST_CACHE: dict[
    int, tuple[Any, tuple, tuple[list[float], list[float], list[float], list[float], list[float], list[float]]]
] = {}
_OHLCV_LIST_CACHE_MAX = 8

# Synthetic bar-open spacing when host omits ``time`` (matches CompiledScript.run).
_SYNTHETIC_BAR_MS = 60_000.0

# Script declaration header for compile-path envelope (AXIS pane routing).
_SCRIPT_HEADER_RE = re.compile(
    r"(?m)^\s*(indicator|strategy|library|study)\s*\("
    r"\s*(?:\"([^\"]*)\"|'([^']*)')?",
)
_OVERLAY_KW_RE = re.compile(r"\boverlay\s*=\s*(true|false)\b", re.IGNORECASE)


def _ohlcv_pack_fingerprint(ohlcv_data: list[dict]) -> tuple:
    n = len(ohlcv_data)
    if n == 0:
        return (0,)
    first = ohlcv_data[0]
    last = ohlcv_data[-1]
    return (
        n,
        first.get("time"),
        last.get("time"),
        first.get("close"),
        last.get("close"),
    )


def _coerce_ohlc_cell(value: Any, default: float = 0.0) -> float:
    """Host OHLC cell → finite float (None / bad → ``default``; never silent na→0 in Pine)."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_volume_cell(value: Any) -> float:
    """Host volume cell. Missing/None/invalid → ``1.0`` (engine + compile default)."""
    if value is None:
        return 1.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0


def _coerce_time_cell(raw: Any, bar_index: int) -> float:
    """Bar-open Unix ms. Missing/invalid → synthetic ``bar_index * 60_000``."""
    if raw is None:
        return float(bar_index) * _SYNTHETIC_BAR_MS
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(bar_index) * _SYNTHETIC_BAR_MS


def _pack_ohlcv_columns(
    ohlcv_data: list[dict],
) -> tuple[list[float], list[float], list[float], list[float], list[float], list[float]]:
    """Pack OHLCV dict rows into parallel Python float lists (open..volume, time).

    **Single host contract** for interpret bar columns and compile numpy arrays:

    - OHLC missing / ``None`` / non-numeric → ``0.0``
    - volume missing / ``None`` / non-numeric → ``1.0`` (not ``0.0``)
    - time missing / invalid → synthetic ``bar_index * 60_000``

    Do not diverge defaults between modes — packing-only drift is a host bug.
    """
    n = len(ohlcv_data)
    if n == 0:
        empty: list[float] = []
        return empty, empty, empty, empty, empty, empty

    o_l: list[float] = []
    h_l: list[float] = []
    l_l: list[float] = []
    c_l: list[float] = []
    v_l: list[float] = []
    t_l: list[float] = []
    oa, ha, la, ca, va, ta = (
        o_l.append,
        h_l.append,
        l_l.append,
        c_l.append,
        v_l.append,
        t_l.append,
    )
    for i, b in enumerate(ohlcv_data):
        if not isinstance(b, dict):
            oa(0.0)
            ha(0.0)
            la(0.0)
            ca(0.0)
            va(1.0)
            ta(float(i) * _SYNTHETIC_BAR_MS)
            continue
        # Hot path: required OHLC keys (KeyError → safe defaults)
        try:
            o = b["open"]
            h = b["high"]
            l = b["low"]
            c = b["close"]
        except KeyError:
            o = b.get("open", 0.0)
            h = b.get("high", 0.0)
            l = b.get("low", 0.0)
            c = b.get("close", 0.0)
        oa(_coerce_ohlc_cell(o))
        ha(_coerce_ohlc_cell(h))
        la(_coerce_ohlc_cell(l))
        ca(_coerce_ohlc_cell(c))
        if "volume" in b:
            va(_coerce_volume_cell(b.get("volume")))
        else:
            va(1.0)
        ta(_coerce_time_cell(b.get("time"), i))
    return o_l, h_l, l_l, c_l, v_l, t_l


def _pack_ohlcv_columns_cached(
    ohlcv_data: list[dict],
) -> tuple[list[float], list[float], list[float], list[float], list[float], list[float]]:
    """Identity-cached Python columns from :func:`_pack_ohlcv_columns`.

    Interpret bar loop indexes these lists every bar. Warm re-eval of the
    same ``ohlcv_data`` object (bench / Pro re-run) skips the dict walk.
    """
    oid = id(ohlcv_data)
    fp = _ohlcv_pack_fingerprint(ohlcv_data)
    hit = _OHLCV_LIST_CACHE.get(oid)
    if hit is not None and hit[0] is ohlcv_data and hit[1] == fp:
        return hit[2]
    packed = _pack_ohlcv_columns(ohlcv_data)
    if len(_OHLCV_LIST_CACHE) >= _OHLCV_LIST_CACHE_MAX:
        try:
            _OHLCV_LIST_CACHE.pop(next(iter(_OHLCV_LIST_CACHE)))
        except StopIteration:
            pass
    _OHLCV_LIST_CACHE[oid] = (ohlcv_data, fp, packed)
    return packed


def _ohlcv_dicts_to_arrays(ohlcv_data: list[dict]) -> tuple[Any, Any, Any, Any, Any]:
    """Pack OHLCV dict rows into float64 numpy arrays (shared host contract).

    Uses :func:`_pack_ohlcv_columns` then one ``asarray`` per column. Caches by
    list identity + fingerprint for warm re-runs (bench / re-eval same bars).
    Returns ``(open, high, low, close, volume)``; use :func:`_ohlcv_times_to_array`
    (or the shared pack cache entry) for ``time``.
    """
    packed6 = _ohlcv_pack_cached(ohlcv_data)
    return packed6[0], packed6[1], packed6[2], packed6[3], packed6[4]


def _ohlcv_times_to_array(ohlcv_data: list[dict]) -> Any:
    """Bar-open Unix ms for both modes (same synthetic fallback as interpret).

    Missing/invalid times fall back to synthetic ``bar_index * 60_000`` so
    length always matches OHLCV. Shares the OHLCV pack cache with volume packing.
    """
    return _ohlcv_pack_cached(ohlcv_data)[5]


def _ohlcv_pack_cached(
    ohlcv_data: list[dict],
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Identity-cached ``(o, h, l, c, v, t)`` float64 arrays."""
    import numpy as np  # noqa: PLC0415

    oid = id(ohlcv_data)
    fp = _ohlcv_pack_fingerprint(ohlcv_data)
    hit = _OHLCV_PACK_CACHE.get(oid)
    if hit is not None and hit[0] is ohlcv_data and hit[1] == fp:
        return hit[2]

    o_l, h_l, l_l, c_l, v_l, t_l = _pack_ohlcv_columns_cached(ohlcv_data)
    if not o_l:
        z = np.empty(0, dtype=np.float64)
        packed = (z, z, z, z, z, z)
    else:
        packed = (
            np.asarray(o_l, dtype=np.float64),
            np.asarray(h_l, dtype=np.float64),
            np.asarray(l_l, dtype=np.float64),
            np.asarray(c_l, dtype=np.float64),
            np.asarray(v_l, dtype=np.float64),
            np.asarray(t_l, dtype=np.float64),
        )
    if len(_OHLCV_PACK_CACHE) >= _OHLCV_PACK_CACHE_MAX:
        try:
            _OHLCV_PACK_CACHE.pop(next(iter(_OHLCV_PACK_CACHE)))
        except StopIteration:
            pass
    _OHLCV_PACK_CACHE[oid] = (ohlcv_data, fp, packed)
    return packed


def _parse_script_header_fields(source_code: str) -> dict[str, Any]:
    """Best-effort declaration fields for compile-path series envelope.

    Interpret reads ``evaluator._script_declaration`` after the bar loop.
    Compile never walks the AST for AXIS meta — parse title / type / overlay
    from the declaration line so both modes expose the same envelope keys.
    """
    script_type = "indicator"
    script_name = "plot"
    # Pine defaults: indicator overlay=false; strategy overlay=true.
    overlay = False
    src = source_code or ""
    m = _SCRIPT_HEADER_RE.search(src)
    if m:
        kind = (m.group(1) or "indicator").lower()
        if kind == "study":
            kind = "indicator"
        script_type = kind
        title = m.group(2) if m.group(2) is not None else m.group(3)
        if title is not None and str(title).strip():
            script_name = str(title).strip()
        overlay = kind == "strategy"
    om = _OVERLAY_KW_RE.search(src)
    if om:
        overlay = om.group(1).lower() == "true"
    return {
        "script_type": script_type,
        "script_name": script_name,
        "overlay": overlay,
    }


def _compile_plot_meta(json_series: dict[str, list[Any]]) -> dict[str, dict[str, Any]]:
    """Minimal ``plot_meta`` for compile mode (titles + index; style unknown)."""
    meta: dict[str, dict[str, Any]] = {}
    for i, title in enumerate(json_series.keys()):
        meta[title] = {
            "title": title,
            "color": None,
            "linewidth": 1,
            "index": i,
            "kind": "plot",
        }
    return meta


def _stamp_compile_plot_kinds(
    plot_meta: dict[str, dict[str, Any]],
    titles: list[str] | None,
    kinds: list[str] | None,
) -> None:
    """Overlay compiler plot kinds (hline/fill/…) onto compile plot_meta."""
    if not plot_meta or not titles:
        return
    kind_list = list(kinds or [])
    used: set[str] = set()
    for i, raw in enumerate(titles):
        kind = kind_list[i] if i < len(kind_list) else "plot"
        base = raw if isinstance(raw, str) and raw.strip() else f"plot_{i}"
        key = base
        suffix = 2
        while key in used:
            key = f"{base}_{suffix}"
            suffix += 1
        used.add(key)
        if not kind:
            continue
        entry = plot_meta.get(key)
        if entry is not None and entry.get("kind") in (None, "plot"):
            entry["kind"] = kind


def _clear_pine_call_sites(tree: Any) -> None:
    """Drop evaluator-bound call-site caches from a shared AST tree.

    ``visit_Call`` stores ``_pine_call_site`` on AST nodes (bound handlers from
    the evaluator that first resolved the site). Package ``parse`` caches trees
    by source hash; without this clear, a second ``Runtime`` reuses the *first*
    evaluator's ``plot`` / ``ta.*`` handlers (empty plots / wrong state).

    Clear once at run start; bar 0 rebinds for the current evaluator.
    """
    try:
        for node in walk(tree):
            if getattr(node, "_pine_call_site", None) is not None:
                try:
                    delattr(node, "_pine_call_site")
                except Exception:
                    try:
                        object.__setattr__(node, "_pine_call_site", None)
                    except Exception:
                        pass
    except Exception:
        pass


def _discard_realtime_plot_tick(evaluator: Any) -> None:
    """Drop plot cells appended for an intermediate realtime tick on the same bar.

    Multi-tick realtime simulation re-visits the script without advancing
    ``_plot_bars_done``; intermediate ticks must not leave extra series cells.
    Pre-sized columns overwrite the same bar slot — only reset the capture index.
    """
    if int(getattr(evaluator, "_plot_n_bars", 0) or 0) > 0:
        try:
            evaluator._plot_capture_i = 0
        except Exception:
            pass
        return
    n = int(getattr(evaluator, "_plot_capture_i", 0) or 0)
    cols = getattr(evaluator, "_plot_value_cols", None)
    if cols and n > 0:
        limit = n if n < len(cols) else len(cols)
        for j in range(limit):
            col = cols[j]
            if col:
                col.pop()
    try:
        evaluator._plot_capture_i = 0
    except Exception:
        pass


def _parse_script(source_code: str) -> Any:
    """Parse Pine source for Runtime (shared package-level AST cache).

    Caching and invalidation are owned by :func:`pynescript.ast.helper.parse`
    (``clear_parse_cache``, ``PYNE_PARSE_CACHE=0``). Shared trees are scrubbed of
    bound call-site caches so multi-run reuse stays correct.
    """
    tree = parse(source_code, mode="exec")
    _clear_pine_call_sites(tree)
    return tree


class Syminfo:
    """Symbol information namespace for Pine Script builtins.

    Contains information about the current symbol like ticker, currency, etc.
    Added in Pine Script v5, with isin and current_contract added in 2025.
    """

    # Basic symbol info (existing)
    tickerid: str = "AAPL"
    currency: str = "USD"
    type: str = "stock"
    session: str = "regular"
    tick_size: float = 0.01
    pointvalue: float = 1.0
    mintick: float = 0.01
    description: str = "Apple Inc."
    strategy_type: str = "long"
    prefix: str = "NASDAQ"
    name: str = "AAPL"
    # Bare ticker without exchange (TV ``syminfo.ticker`` property)
    ticker: str = "AAPL"
    # Root of continuous futures / same as ticker for stocks
    root: str = "AAPL"
    # Exchange IANA timezone (TV ``syminfo.timezone``)
    timezone: str = "UTC"

    # November 2025: ISIN (International Securities Identification Number)
    isin: str = ""  # 12-character ISIN code, empty string if not available

    # July 2025: Current contract for continuous futures
    current_contract: str | None = None  # Ticker ID of underlying contract for continuous futures

    # November 2024: Minimum contract size
    mincontract: int = 1


class Chartinfo:
    """Chart information namespace for Pine Script builtins."""

    type: str = "candle"
    aggtype: str = "Standard"
    time: int = 0
    status: str = "regular"


class Timeframe:
    """Timeframe information namespace for Pine Script builtins.

    Attribute names match TradingView Pine: ``isdaily`` / ``ismonthly`` /
    ``isdwm`` (not ``is_daily``). Defaults assume a daily chart.
    """

    period: str = "D"  # e.g., "1D", "1H", "5"
    multiplier: int = 1
    isintraday: bool = False
    isdaily: bool = True
    isweekly: bool = False
    ismonthly: bool = False
    isseconds: bool = False
    isinseconds: bool = False
    isminutes: bool = False
    ishours: bool = False
    isdwm: bool = True
    current: str = "D"

    # November 2024: Main period from chart's main context
    main_period: str = "D"

    # Back-compat aliases
    is_daily: bool = True
    is_weekly: bool = False
    is_monthly: bool = False
    is_seconds: bool = False


class Barstate:
    """Bar state information namespace for Pine Script builtins."""

    isfirst: bool = False
    islast: bool = False
    isnew: bool = True
    ishistory: bool = True
    isconfirmed: bool = True
    islastconfirmedhistory: bool = False
    isrealtime: bool = False
    iscomposite: bool = False


class Chart:
    """Chart namespace for Pine Script builtins.

    Pine uses ununderscored names (``is_heikinashi``); keep snake_case aliases
    for older hosts and bind both on instances.
    """

    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    resolution: str = "D"

    # Chart display mode (Python-style + Pine-style aliases)
    is_heikin_ashi: bool = False
    is_heikinashi: bool = False
    is_kagi: bool = False
    is_line_break: bool = False
    is_linebreak: bool = False
    is_point_figure: bool = False
    is_pointfigure: bool = False
    is_pnf: bool = False  # TV name for point-and-figure
    is_renko: bool = False
    is_range: bool = False
    is_standard: bool = True
    # Viewport (host may override; Runtime seeds from bar range)
    left_visible_bar_time: int | float = 0
    right_visible_bar_time: int | float = 0


class Runtime:
    """Bar-mode host that evaluates Pine over OHLCV (interpret / compile / auto).

    Builds symbol namespaces, seeds series history, captures plots via
    :class:`~pynescript.runtime.evaluator.CustomEvaluator`, and returns a
    JSON-friendly result dict for AXIS and the Pro API.
    """

    def __init__(self, symbol: str = "AAPL", run_id: str | None = None):
        """Initialize the runtime with optional symbol configuration.

        Args:
            symbol: The symbol to use for the runtime (default: "AAPL")
            run_id: Optional unique run identifier. Generated if not provided.
        """
        self.symbol = symbol
        self._run_id = run_id or uuid.uuid4().hex[:16]
        self._syminfo = Syminfo()
        self._syminfo.tickerid = symbol
        self._syminfo.prefix = self._extract_prefix(symbol)
        bare = self._extract_ticker(symbol)
        self._syminfo.ticker = bare
        self._syminfo.root = bare
        # ``name`` is the bare ticker in TV for most asset classes
        self._syminfo.name = bare or symbol

        # February 2025: bid/ask variables (only available on 1T timeframe)
        self._bid: float | None = None
        self._ask: float | None = None

        # November 2024: main ticker reference
        self._main_tickerid: str = symbol

    def _extract_prefix(self, symbol: str) -> str:
        """Extract prefix from symbol (e.g., 'NASDAQ' from 'NASDAQ:AAPL')."""
        if ":" in symbol:
            return symbol.split(":", maxsplit=1)[0]
        return ""

    def _extract_ticker(self, symbol: str) -> str:
        """Extract bare ticker from symbol (e.g., 'AAPL' from 'NASDAQ:AAPL')."""
        if ":" in symbol:
            return symbol.split(":", maxsplit=1)[1]
        return symbol

    def _make_chart(self, ohlcv_data: list | None = None) -> Chart:
        """Build a Chart host object seeded with viewport times from bars."""
        chart = Chart()
        if ohlcv_data:
            first_t = ohlcv_data[0].get("time", 0) or 0
            last_t = ohlcv_data[-1].get("time", 0) or 0
            chart.left_visible_bar_time = first_t
            chart.right_visible_bar_time = last_t
        return chart

    def configure_footprint(self, footprint_data: dict) -> None:
        """Configure syminfo based on footprint data.

        Args:
            footprint_data: Dictionary containing footprint configuration
        """
        if "isin" in footprint_data:
            self._syminfo.isin = footprint_data["isin"]
        if "current_contract" in footprint_data:
            self._syminfo.current_contract = footprint_data["current_contract"]

    def update_bid_ask(self, bid: float | None, ask: float | None) -> None:
        """Update bid/ask prices (February 2025 feature).

        Args:
            bid: Bid price (highest buy order)
            ask: Ask price (lowest sell order)
        """
        self._bid = bid
        self._ask = ask

    def run(
        self,
        source_code: str,
        ohlcv_data: list[dict],
        data_feed=None,
        data_provider=None,
        mode: str | None = None,
        inputs: dict | None = None,
        profiler: bool = False,
        timeout_seconds: float | None = None,
        libraries: list[dict[str, Any]] | None = None,
        *,
        realtime_last_bar: bool = False,
        realtime_ticks: int = 1,
        realtime_bars: int = 0,
        realtime_from_bar: int | None = None,
    ):
        """
        Execute the script over the provided OHLCV data.

        Args:
            source_code: Pine Script source to run.
            ohlcv_data: List of dicts with 'open', 'high', 'low', 'close', 'time'.
            data_feed: Optional realtime DataFeed for request.* live data.
            data_provider: Optional historical provider for request.* .
            mode:
                ``"interpret"`` — AST walker.
                ``"compile"`` — Numba (numeric) or pure-Python object bar loop.
                ``"auto"`` — try compile; on eligibility fail / compile error /
                runtime error fall back to interpret (reason in
                ``compile_fallback_reason``). Non-empty ``inputs`` skip compile
                (overrides not applied on compile path).
                Default when omitted: ``PYNE_RUNTIME_MODE`` env, else
                ``"interpret"``. Pro API ``RUN_SCHEMA`` defaults body ``mode``
                to ``"auto"`` when the field is absent.
            inputs: Optional Pine ``input.*`` overrides keyed by title.
                Applied on interpret only; auto with overrides uses interpret.
            profiler: When true, collect per-line timings for AXIS gutter.
                Forces interpret (compile has no statement walk).
            libraries: Optional list of ``{namespace, name, version, source}``
                dicts registered via ``register_library_source`` before
                ``import ns/Name/ver`` resolves (AXIS git publish emulator).
            timeout_seconds: Optional wall-clock budget (edge workers / cron).
                When exceeded, interpret stops early and returns partial
                results with ``timed_out=True`` and ``error`` set.
                ``None`` = no limit. Checked every 32 bars on the hot path.
            realtime_last_bar: Interpret only. When true, the last bar is
                visited with ``barstate.isrealtime=True`` (forming bar:
                ``ishistory=False``). Default false keeps historical hosts
                unchanged (``isrealtime`` always false). Ignored when
                ``realtime_bars > 0`` or ``realtime_from_bar`` is set (those
                define a multi-bar realtime window instead).
            realtime_ticks: Interpret only. How many times to re-visit each
                bar in the realtime window. Values ``>1`` also enable last-bar
                realtime when no window is set via ``realtime_bars`` /
                ``realtime_from_bar`` (same as ``realtime_last_bar=True``).
                Intermediate ticks discard plot cells so series length stays
                one sample per bar; final tick keeps ``varip`` re-init
                semantics from the evaluator. Default ``1``.
            realtime_bars: Interpret only. When ``>0``, the last *K* bars
                (``[n_bars - K, n_bars)``) are treated as realtime-forming
                with multi-tick re-eval. Historical bars before that window
                stay ``ishistory=True`` / ``isrealtime=False``. Default ``0``
                keeps legacy last-bar-only behavior when
                ``realtime_last_bar`` / ``realtime_ticks`` are used.
            realtime_from_bar: Interpret only. Absolute start index of the
                realtime window ``[realtime_from_bar, n_bars)``. When set,
                overrides ``realtime_bars`` and last-bar-only flags for
                window extent. Clamped to ``[0, n_bars)``. ``None`` (default)
                does not open a window by itself.

        Returns:
            dict with 'series': list of plotted values for each bar.
            Auto mode also sets ``auto_backend`` (``compile``|``interpret``)
            and may set ``compile_fallback_reason``.
        """
        if mode is None or mode == "":
            mode = os.environ.get("PYNE_RUNTIME_MODE", "interpret")
        mode_norm = (mode or "interpret").strip().lower()
        # Line profiler needs the AST walker — skip compile when enabled.
        if profiler and mode_norm in ("compile", "auto"):
            mode_norm = "interpret"
        if mode_norm == "compile":
            return self._run_compiled(source_code, ohlcv_data)
        if mode_norm == "auto":
            return self._run_auto(
                source_code,
                ohlcv_data,
                data_feed=data_feed,
                data_provider=data_provider,
                inputs=inputs,
                timeout_seconds=timeout_seconds,
                libraries=libraries,
            )
        if mode_norm not in ("interpret",):
            return _error_payload(
                f"Unknown mode: {mode!r} (use interpret|compile|auto)",
                kind=ERROR_KIND_MODE,
            )
        # Stash for interpret bar loop (avoids threading through every helper).
        self._timeout_seconds = timeout_seconds

        t_total0 = time.perf_counter()
        # Fresh log buffer per run so messages never leak across /run calls.
        _clear_pine_logger()
        n_bars_hint = len(ohlcv_data) if ohlcv_data else 0

        # Wire request.* sources: chart bars as historical provider when unset.
        # Soft-fail by design: missing/broken feeds fall back to request.* mocks.
        try:
            from pynescript.util.data import resolve_request_sources

            data_feed, data_provider = resolve_request_sources(
                data_feed=data_feed,
                data_provider=data_provider,
                chart_bars=ohlcv_data,
                symbol=getattr(self, "symbol", "CHART") or "CHART",
            )
        except Exception:  # noqa: BLE001 — intentional soft-fail → mock data
            pass

        # Parse once (cached by source hash for multi-run hosts)
        t_parse0 = time.perf_counter()
        try:
            tree = _parse_script(source_code)
        except Exception as e:
            parse_ms = (time.perf_counter() - t_parse0) * 1000.0
            return _attach_logs_profile(
                _error_payload(
                    _format_exc_message("Parse Error", e),
                    kind=ERROR_KIND_PARSE,
                    exc=e,
                ),
                total_ms=(time.perf_counter() - t_total0) * 1000.0,
                bars=n_bars_hint,
                mode="interpret",
                parse_ms=parse_ms,
                eval_ms=0.0,
            )
        parse_ms = (time.perf_counter() - t_parse0) * 1000.0
        t_eval0 = time.perf_counter()

        # Initialize Series (PYNE_SERIES_RING=1 → chronological O(1) lookback).
        # Default off: classic PineSeries (newest-first deque). When the ring
        # is on, current_series is a tail view (no dual list write). History
        # length follows max_bars_back / PYNE_SERIES_MAX when larger than 1000.
        _cap_on = series_cap_enabled()
        _mbb_decl = parse_max_bars_back_from_source(source_code)
        _host_series_cap = resolve_series_cap(max_bars_back=_mbb_decl)
        _ps_hist = pineseries_history_length(series_cap=_host_series_cap)
        open_series = make_pine_series(history_length=_ps_hist)
        high_series = make_pine_series(history_length=_ps_hist)
        low_series = make_pine_series(history_length=_ps_hist)
        close_series = make_pine_series(history_length=_ps_hist)
        volume_series = make_pine_series(history_length=_ps_hist)
        hl2_series = make_pine_series(history_length=_ps_hist)
        hlc3_series = make_pine_series(history_length=_ps_hist)
        ohlc4_series = make_pine_series(history_length=_ps_hist)
        tr_series = make_pine_series(history_length=_ps_hist)  # true range
        # time / time_close are series (time[1] = previous bar open time). Scalar
        # overwrite broke history lookbacks used by year_sum-style TTM windows.
        time_series = make_pine_series(history_length=_ps_hist)
        time_close_series = make_pine_series(history_length=_ps_hist)

        # Context initialization (daily chart defaults).
        # LazyCalendarContext: calendar series (year/month/…) materialise on read.
        tf = Timeframe()
        barstate = Barstate()
        context: LazyCalendarContext = LazyCalendarContext(
            {
                "open": open_series,
                "high": high_series,
                "low": low_series,
                "close": close_series,
                "volume": volume_series,
                "hl2": hl2_series,
                "hlc3": hlc3_series,
                "ohlc4": ohlc4_series,
                "tr": tr_series,
                # Symbol info namespace (November 2025: syminfo.isin, July 2025: syminfo.current_contract)
                "syminfo": self._syminfo,
                "timeframe": tf,
                "barstate": barstate,
                "chart": self._make_chart(ohlcv_data),
                "timeframe.period": tf.period,
                "timeframe.main_period": tf.main_period,
                "timeframe.multiplier": tf.multiplier,
                "timeframe.isintraday": tf.isintraday,
                "timeframe.isdaily": tf.isdaily,
                "timeframe.isweekly": tf.isweekly,
                "timeframe.ismonthly": tf.ismonthly,
                "timeframe.isseconds": tf.isseconds,
                "timeframe.isinseconds": tf.isinseconds,
                "timeframe.isdwm": tf.isdwm,
                # Per-bar counters updated in the loop below.
                # last_bar_time is filled after shared OHLCV packing (synthetic time
                # when host omits bar times — same as compile time_arr).
                "bar_index": 0,
                "time": time_series,
                "time_close": time_close_series,
                "last_bar_index": max(0, len(ohlcv_data) - 1),
                "last_bar_time": 0,
            }
        )

        evaluator = CustomEvaluator(context=context, data_feed=data_feed, data_provider=data_provider)
        evaluator.reset_var_declarations()
        for lib in libraries or []:
            if not isinstance(lib, dict):
                continue
            ns = str(lib.get("namespace") or "")
            name = str(lib.get("name") or "")
            src = str(lib.get("source") or "")
            try:
                ver = int(lib.get("version") or 1)
            except (TypeError, ValueError):
                ver = 1
            if ns and name and src:
                try:
                    evaluator.register_library_source(ns, name, ver, src)
                except Exception:
                    pass
        # Host UI overrides for input.* (keyed by title)
        if inputs and isinstance(inputs, dict):
            try:
                evaluator._input_overrides = dict(inputs)  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            evaluator._input_declarations = []  # type: ignore[attr-defined]
        except Exception:
            pass
        # Per-line timing map (line → [ms_sum, execs]); visit_Script aggregates.
        if profiler:
            try:
                evaluator._pine_line_profile = {}  # type: ignore[attr-defined]
            except Exception:
                pass

        # Phase 2.5: corpus / success-only — skip plot columns + input meta (default off).
        light_plots = _env_truthy("PYNE_LIGHT_PLOTS")
        evaluator._pine_light_plots = light_plots  # type: ignore[attr-defined]
        # fill() needs plot() → Plot handles; skip PlotRegistry otherwise (big host win).
        # Light mode never needs registry (fill soft-fails; corpus only cares OK/fail).
        if light_plots:
            evaluator._pine_need_plot_ids = False  # type: ignore[attr-defined]
        else:
            evaluator._pine_need_plot_ids = bool(_FILL_CALL_RE.search(source_code))  # type: ignore[attr-defined]

        # Append-only chronological OHLCV lists for ta.* helpers (oldest → newest).
        # Avoid rebuilding via list(reversed(PineSeries.history)) every bar.
        # Ring path replaces these with ChronoTailView after series_cap is known.
        _use_ring = series_ring_enabled()
        _series_lists: dict[str, list] = {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "hl2": [],
            "hlc3": [],
            "ohlc4": [],
            "tr": [],
        }
        evaluator.current_series = _series_lists

        # Fresh drawing registries so leftover labels/lines from prior runs
        # (or tests) do not leak into this response.
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            DrawingRegistry.reset()
        except Exception:
            pass

        # Alert engine: clear per-run so prior jobs do not leak firings
        clear_alerts = getattr(evaluator, "clear_alerts", None)
        if callable(clear_alerts):
            try:
                clear_alerts()
            except Exception:
                pass

        all_events: list[dict] = []
        all_events_append = all_events.append

        # Generate stable script_id from source hash
        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]
        run_id = self._run_id

        n_bars = len(ohlcv_data)
        last_bar_i = n_bars - 1
        # Pre-size plot columns so capture writes by bar index (no append/resize).
        evaluator._plot_n_bars = n_bars  # type: ignore[attr-defined]
        # Shared host packing (same volume/time defaults as mode=compile).
        # Cached by list identity so warm interpret re-runs skip the dict walk.
        col_open, col_high, col_low, col_close, col_vol, col_time = _pack_ohlcv_columns_cached(ohlcv_data)
        if col_time:
            context["last_bar_time"] = col_time[-1]
            # Chart viewport times track packed bar-open ms (incl. synthetic).
            try:
                chart = context.get("chart")
                if chart is not None:
                    chart.left_visible_bar_time = int(col_time[0])
                    chart.right_visible_bar_time = int(col_time[-1])
            except Exception:
                pass
        has_bid_ask = False
        for b in ohlcv_data:
            if isinstance(b, dict) and (("bid" in b) or ("ask" in b)):
                has_bid_ask = True
                break
        # input.source can pick derived names that never appear as identifiers.
        need_src_input = bool(_INPUT_SOURCE_RE.search(source_code))
        need_hl2 = need_src_input or bool(_HL2_RE.search(source_code))
        need_hlc3 = need_src_input or bool(_HLC3_RE.search(source_code)) or bool(_VWAP_RE.search(source_code))
        need_ohlc4 = need_src_input or bool(_OHLC4_RE.search(source_code))
        need_tr = need_src_input or bool(_TR_RE.search(source_code))
        need_time_close = bool(_TIME_CLOSE_RE.search(source_code))
        need_strategy = bool(_STRATEGY_NAME_RE.search(source_code))
        need_alerts = bool(_ALERT_CALL_RE.search(source_code))
        need_cross = "crossover" in source_code or "crossunder" in source_code or "ta.cross(" in source_code

        # Pre-bind hot locals (series lists, methods, strategy buffers)
        sl_open = _series_lists["open"]
        sl_high = _series_lists["high"]
        sl_low = _series_lists["low"]
        sl_close = _series_lists["close"]
        sl_vol = _series_lists["volume"]
        sl_hl2 = _series_lists["hl2"]
        sl_hlc3 = _series_lists["hlc3"]
        sl_ohlc4 = _series_lists["ohlc4"]
        sl_tr = _series_lists["tr"]
        # Keep a tuple of list refs for in-place series-cap trim (no rebind).
        # Only include lists that are actually appended each bar.
        _series_list_refs_list = [sl_open, sl_high, sl_low, sl_close, sl_vol]
        if need_tr:
            _series_list_refs_list.append(sl_tr)
        if need_hl2:
            _series_list_refs_list.append(sl_hl2)
        if need_hlc3:
            _series_list_refs_list.append(sl_hlc3)
        if need_ohlc4:
            _series_list_refs_list.append(sl_ohlc4)
        _series_list_refs = tuple(_series_list_refs_list)
        # T1: cap append-only current_series to max_bars_back / _SERIES_MAX.
        # Flag PYNE_SERIES_CAP (default ON). Disable with PYNE_SERIES_CAP=0.
        _ev_series_max = int(getattr(evaluator, "_SERIES_MAX", 256) or 256)
        series_cap = resolve_series_cap(
            series_max=_ev_series_max,
            max_bars_back=_mbb_decl,
        )
        # Prefer host resolution already computed; re-resolve if evaluator
        # exposed a different _SERIES_MAX (keep max of both bases).
        if series_cap < _host_series_cap:
            # Keep the larger of pre-eval host cap and evaluator-based cap.
            series_cap = max(series_cap, _host_series_cap)
        _do_series_cap = _cap_on
        _series_trim_limit = series_cap_limit(series_cap) if _do_series_cap else 0
        # Short charts never hit the slack limit — skip the per-bar length check.
        if _do_series_cap and n_bars <= _series_trim_limit:
            _do_series_cap = False
        # Stash for tests / hosts that inspect the last run policy.
        try:
            evaluator._pine_series_cap = series_cap if _do_series_cap else None  # type: ignore[attr-defined]
            evaluator._pine_series_cap_enabled = _do_series_cap  # type: ignore[attr-defined]
        except Exception:
            pass

        if _use_ring:
            from pynescript.ast.evaluator.series_buffer import ChronoTailView

            # Cap-off: expose the full ring window (history floor / max_bars_back).
            _tail_keep = series_cap if _do_series_cap else _ps_hist

            def _tail(series: Any) -> ChronoTailView:
                return ChronoTailView(series.buffer, keep=_tail_keep)

            evaluator.current_series = {
                "open": _tail(open_series),
                "high": _tail(high_series),
                "low": _tail(low_series),
                "close": _tail(close_series),
                "volume": _tail(volume_series),
                "hl2": _tail(hl2_series),
                "hlc3": _tail(hlc3_series),
                "ohlc4": _tail(ohlc4_series),
                "tr": _tail(tr_series),
            }
            _do_series_cap = False  # no list prefix trim; view already windows
            sl_open = sl_high = sl_low = sl_close = sl_vol = sl_tr = None
            sl_hl2 = sl_hlc3 = sl_ohlc4 = None
            _series_list_refs = ()

        # Inline .current + history.appendleft (works for deque and ring view).
        # Avoids a Python PineSeries.update call per series per bar.
        open_al = open_series.history.appendleft
        high_al = high_series.history.appendleft
        low_al = low_series.history.appendleft
        close_al = close_series.history.appendleft
        volume_al = volume_series.history.appendleft
        time_al = time_series.history.appendleft
        hl2_al = hl2_series.history.appendleft if need_hl2 else None
        hlc3_al = hlc3_series.history.appendleft if need_hlc3 else None
        ohlc4_al = ohlc4_series.history.appendleft if need_ohlc4 else None
        tr_al = tr_series.history.appendleft if need_tr else None
        time_close_al = time_close_series.history.appendleft if need_time_close else None

        # Historical defaults. Opt-in realtime window overrides
        # isrealtime / ishistory / isconfirmed / isnew per tick below.
        barstate.isnew = True
        barstate.ishistory = True
        barstate.isconfirmed = True
        barstate.isrealtime = False
        try:
            _rt_ticks = int(realtime_ticks)
        except (TypeError, ValueError):
            _rt_ticks = 1
        if _rt_ticks < 1:
            _rt_ticks = 1
        try:
            _rt_bars = int(realtime_bars)
        except (TypeError, ValueError):
            _rt_bars = 0
        if _rt_bars < 0:
            _rt_bars = 0
        # Resolve realtime window start index (inclusive), or None = historical only.
        # Precedence: realtime_from_bar > realtime_bars > last-bar-only flags.
        _rt_first: int | None = None
        if realtime_from_bar is not None:
            try:
                _rt_first = int(realtime_from_bar)
            except (TypeError, ValueError):
                _rt_first = 0
            if _rt_first < 0:
                _rt_first = 0
            if _rt_first >= n_bars:
                # Window empty → no realtime bars (historical path).
                _rt_first = None
        elif _rt_bars > 0:
            _rt_first = n_bars - _rt_bars if n_bars > _rt_bars else 0
        elif bool(realtime_last_bar) or _rt_ticks > 1:
            # Legacy: last bar only (realtime_ticks>1 implies last-bar multi-pass).
            _rt_first = last_bar_i if n_bars > 0 else None

        visit = evaluator.visit
        reset_plots = evaluator.reset_plots
        finish_bar_plots = evaluator.finish_bar_plots
        strategy_state = evaluator._strategy_state
        pending_orders = strategy_state.pending_orders
        strategy_events = strategy_state._events
        process_pending = getattr(evaluator, "process_pending_orders", None)
        set_defs_locked = True  # first bar unlocks defs; then permanently locked
        # Indicators never read strategy.*[n] — skip 3 list appends per bar.
        snapshot_bar = getattr(strategy_state, "snapshot_bar_series", None) if need_strategy else None
        _rt_enabled = _rt_first is not None
        _hist_n = 0
        prev_close_f: float | None = None

        # Wall-clock circuit breaker for Cloudflare / cron / Pro budgets.
        timed_out = False
        timeout_seconds = getattr(self, "_timeout_seconds", None)
        if timeout_seconds is not None:
            deadline = time.monotonic() + float(timeout_seconds)
        else:
            deadline = None

        for bar_index in range(n_bars):
            # Check every 32 bars to keep the hot path cheap.
            if deadline is not None and (bar_index & 31) == 0 and time.monotonic() > deadline:
                timed_out = True
                break
            o = col_open[bar_index]
            h = col_high[bar_index]
            l = col_low[bar_index]
            c = col_close[bar_index]
            v = col_vol[bar_index]

            # Packed columns are already host-contract floats — no per-bar float().
            # Inline current + appendleft (deque / ring view). Skip unused derived.
            open_series.current = o
            open_al(o)
            high_series.current = h
            high_al(h)
            low_series.current = l
            low_al(l)
            close_series.current = c
            close_al(c)
            volume_series.current = v
            volume_al(v)
            if need_hl2:
                hl2_val = (h + l) * 0.5
                hl2_series.current = hl2_val
                hl2_al(hl2_val)
                if sl_hl2 is not None:
                    sl_hl2.append(hl2_val)
            if need_hlc3:
                hlc3_val = (h + l + c) / 3.0
                hlc3_series.current = hlc3_val
                hlc3_al(hlc3_val)
                if sl_hlc3 is not None:
                    sl_hlc3.append(hlc3_val)
            if need_ohlc4:
                ohlc4_val = (o + h + l + c) * 0.25
                ohlc4_series.current = ohlc4_val
                ohlc4_al(ohlc4_val)
                if sl_ohlc4 is not None:
                    sl_ohlc4.append(ohlc4_val)
            if need_tr:
                if prev_close_f is None:
                    tr_val = h - l
                else:
                    tr_val = max(h - l, abs(h - prev_close_f), abs(l - prev_close_f))
                prev_close_f = c
                tr_series.current = tr_val
                tr_al(tr_val)
                if sl_tr is not None:
                    sl_tr.append(tr_val)

            # Append-only chronological lists for ta.* (shared with evaluator.current_series).
            # Cap in-place (del prefix) so pre-bound list refs stay valid (T1).
            # Ring path: current_series is a ChronoTailView — no second write.
            if sl_open is not None:
                sl_open.append(o)
                sl_high.append(h)
                sl_low.append(l)
                sl_close.append(c)
                sl_vol.append(v)
                if _do_series_cap:
                    _hist_n += 1
                    if _hist_n > _series_trim_limit:
                        _hist_n = trim_series_lists(
                            _series_list_refs,
                            keep=series_cap,
                            length_hint=_hist_n,
                        )

            # Per-bar counters / time (series update — do not replace PineSeries refs)
            bar_time = col_time[bar_index]
            context["bar_index"] = bar_index
            time_series.current = bar_time
            time_al(bar_time)
            if need_time_close:
                if bar_index < last_bar_i:
                    time_close = col_time[bar_index + 1] or bar_time
                else:
                    time_close = int(bar_time) + 86_400_000
                time_close_series.current = time_close
                time_close_al(time_close)
            # Lazy calendar: record bar time only; year/month/… fill on first read.
            context.set_bar_time(bar_time)

            is_last = bar_index == last_bar_i
            barstate.isfirst = bar_index == 0
            barstate.islast = is_last
            # Realtime multi-tick on bars in the opt-in window. Historical-only
            # hosts keep the pre-loop isnew/ishistory/isconfirmed/isrealtime
            # defaults and only flip islastconfirmedhistory on the last bar.
            if _rt_enabled:
                bar_rt = bar_index >= _rt_first  # type: ignore[operator]
                n_ticks = _rt_ticks if bar_rt else 1
                if not bar_rt:
                    barstate.isnew = True
                    barstate.ishistory = True
                    barstate.isconfirmed = True
                    barstate.isrealtime = False
                    barstate.islastconfirmedhistory = is_last
            else:
                bar_rt = False
                n_ticks = 1
                if is_last:
                    barstate.islastconfirmedhistory = True

            if has_bid_ask:
                bar = ohlcv_data[bar_index]
                if "bid" in bar:
                    self._bid = bar["bid"]
                if "ask" in bar:
                    self._ask = bar["ask"]

            # Broker sim once per bar (before realtime tick re-visits)
            if process_pending is not None and pending_orders:
                try:
                    process_pending(open_=o, high=h, low=l, close=c)
                except Exception as e:
                    eval_ms = (time.perf_counter() - t_eval0) * 1000.0
                    return _attach_logs_profile(
                        _error_payload(
                            _format_exc_message(
                                f"Order fill error at bar {bar_time} (index {bar_index})",
                                e,
                            ),
                            kind=ERROR_KIND_ORDER,
                            exc=e,
                            bar_index=bar_index,
                            bar_time=bar_time,
                        ),
                        total_ms=(time.perf_counter() - t_total0) * 1000.0,
                        bars=n_bars,
                        mode="interpret",
                        parse_ms=parse_ms,
                        eval_ms=eval_ms,
                    )

            for tick_i in range(n_ticks):
                if bar_rt:
                    # Forming bar in realtime window: isrealtime drives varip RHS re-eval.
                    barstate.isrealtime = True
                    barstate.ishistory = False
                    barstate.isnew = tick_i == 0
                    # Final tick models bar confirmation; earlier ticks unconfirmed.
                    barstate.isconfirmed = tick_i == n_ticks - 1
                    barstate.islastconfirmedhistory = False

                # Reset per-bar/tick plot index; clear strategy event buffer
                reset_plots()
                if need_strategy and strategy_events:
                    strategy_events.clear()
                # Always reset TA slots. v4 bare sma/wma, math.sum, and other
                # rolling helpers call ``_ta_next_slot`` even with no ``ta.``
                # in source (gating on ``"ta."`` left those sites all-na).
                if need_cross:
                    evaluator._cross_call_i = 0  # type: ignore[attr-defined]
                evaluator._ta_call_i = 0  # type: ignore[attr-defined]
                evaluator._plot_call_i = 0  # type: ignore[attr-defined]

                try:
                    visit(tree)
                except Exception as e:
                    # Fail closed: never return empty plots for bar-loop exceptions.
                    eval_ms = (time.perf_counter() - t_eval0) * 1000.0
                    return _attach_logs_profile(
                        _error_payload(
                            _format_exc_message(
                                f"Runtime Error at bar {bar_time} (index {bar_index})",
                                e,
                            ),
                            kind=ERROR_KIND_RUNTIME,
                            exc=e,
                            bar_index=bar_index,
                            bar_time=bar_time,
                        ),
                        total_ms=(time.perf_counter() - t_total0) * 1000.0,
                        bars=n_bars,
                        mode="interpret",
                        parse_ms=parse_ms,
                        eval_ms=eval_ms,
                    )

                if tick_i < n_ticks - 1:
                    # Intermediate realtime tick: keep state (var/varip) but
                    # discard plot cells so series length stays 1 per bar.
                    _discard_realtime_plot_tick(evaluator)
                    continue

                # Final tick (or sole historical visit): commit bar outputs.
                if snapshot_bar is not None:
                    snapshot_bar()

                # Pad short plot columns for call sites not hit this bar
                finish_bar_plots()

                # Lock function/type/import registration after first bar (O(bars²) guard)
                if set_defs_locked:
                    evaluator._pine_defs_locked = True  # type: ignore[attr-defined]
                    # Keep assigning True is cheap; skip after first for micro-gain
                    set_defs_locked = False

                # Strategy events (empty for pure indicators — skip drain alloc)
                if need_strategy and strategy_events:
                    for ev in strategy_state.drain_events():
                        ev_dict = ev.to_dict()
                        ev_dict["script_id"] = script_id
                        ev_dict["run_id"] = run_id
                        all_events_append(ev_dict)

        # Build multi-series map from columnar plot capture (value cols + once-only meta).
        # Light mode: skip export packing (corpus only needs error vs OK).
        series_map: dict[str, list[Any]] = {}
        plot_meta: dict[str, dict[str, Any]] = {}
        final_series: list[Any] = []
        n_result_bars = n_bars
        if not light_plots:
            value_cols = getattr(evaluator, "_plot_value_cols", None) or []
            meta_list = getattr(evaluator, "_plot_meta_list", None) or []
            bars_done = int(getattr(evaluator, "_plot_bars_done", 0) or 0)
            pack_dirty = bool(getattr(evaluator, "_plot_pack_dirty", False))
            if value_cols:
                n_result_bars = bars_done if bars_done > 0 else len(value_cols[0])
            series_map, plot_meta, final_series = _pack_interpret_plot_columns(
                value_cols,
                meta_list,
                bars_done=bars_done,
                pack_dirty=pack_dirty,
            )

        # Serialize Pine drawing objects (line/label/box) for AXIS overlay.
        # Fast path: skip bar_times materialization + export when registry empty
        # (most indicator scripts never call line/label/box/table/polyline).
        drawings: list[dict] = []
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            if not DrawingRegistry.is_empty():
                bar_times = [int(t or 0) for t in col_time]
                drawings = DrawingRegistry.export_for_api(bar_times)
        except Exception:
            drawings = []

        # Alert engine export (alert() + true alertcondition firings) — dual-host H1
        # Skip import + walk when the source never calls alert / alertcondition.
        alerts: list[dict[str, Any]] = []
        alert_conditions: list[dict[str, Any]] = []
        if need_alerts:
            try:
                try:
                    from pynescript.ast.evaluator.builtins.alerts import (
                        export_alerts_from_evaluator,
                    )

                    alerts = list(export_alerts_from_evaluator(evaluator) or [])
                except ImportError:
                    raw = getattr(evaluator, "get_triggered_alerts", None)
                    items = raw() if callable(raw) else getattr(evaluator, "_triggered_alerts", None) or []
                    for a in items or []:
                        if hasattr(a, "to_dict"):
                            alerts.append(a.to_dict())
                        elif isinstance(a, dict):
                            alerts.append(dict(a))
                exp_c = getattr(evaluator, "export_alert_conditions", None)
                if callable(exp_c):
                    alert_conditions = list(exp_c() or [])
            except Exception:
                alerts = []
                alert_conditions = []
            for a in alerts:
                if isinstance(a, dict):
                    a.setdefault("script_id", script_id)
                    a.setdefault("run_id", run_id)

        # Script declaration → AXIS pane routing (indicator default overlay=false)
        decl = getattr(evaluator, "_script_declaration", None)
        overlay = True
        script_name = "plot"
        script_type = "indicator"
        if decl is not None:
            script_type = str(getattr(decl, "script_type", "indicator") or "indicator")
            title = str(getattr(decl, "title", "") or "").strip()
            if title:
                script_name = title
            if hasattr(decl, "overlay"):
                overlay = bool(decl.overlay)
            else:
                kw = getattr(decl, "kwargs", None) or {}
                if "overlay" in kw:
                    overlay = bool(kw["overlay"])
                else:
                    overlay = script_type == "strategy"

        # Drawing GC caps for AXIS (from declaration / DrawingRegistry)
        drawing_limits: dict[str, int] = {}
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            drawing_limits = DrawingRegistry.limits_dict()
        except Exception:
            drawing_limits = {}

        # Export input.* declarations for AXIS Script Settings (dedupe by title)
        input_defs: list[dict[str, Any]] = []
        try:
            decls = list(getattr(evaluator, "_input_declarations", None) or [])
            seen_titles: set[str] = set()
            for d in decls:
                if not isinstance(d, dict):
                    continue
                t = str(d.get("title") or "")
                if t and t in seen_titles:
                    continue
                if t:
                    seen_titles.add(t)
                # JSON-safe copy
                safe: dict[str, Any] = {}
                for k, v in d.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        safe[k] = v
                    elif isinstance(v, (list, tuple)):
                        safe[k] = [str(x) if not isinstance(x, (str, int, float, bool, type(None))) else x for x in v]
                    else:
                        safe[k] = str(v)
                input_defs.append(safe)
        except Exception:
            input_defs = []

        eval_ms = (time.perf_counter() - t_eval0) * 1000.0
        total_ms = (time.perf_counter() - t_total0) * 1000.0
        line_rows = _export_line_profile(evaluator) if profiler else []
        meta_out: dict[str, Any] = {
            "overlay": overlay,
            "script_name": script_name,
            "script_type": script_type,
            "inputs": input_defs,
        }
        if drawing_limits:
            meta_out.update(drawing_limits)
        # request.security honesty: policies when no real HTF / multi-symbol feed
        # (complex_htf_na, chart_passthrough_htf_stub, gaps_lookahead_unused, …).
        try:
            sec_pol = getattr(evaluator, "_request_security_policy", None)
            if not isinstance(sec_pol, dict):
                ctx_ev = getattr(evaluator, "context", None) or {}
                sec_pol = ctx_ev.get("request.security_policy") if isinstance(ctx_ev, dict) else None
            if isinstance(sec_pol, dict) and sec_pol.get("calls"):
                # Shallow JSON-safe copy (counts + first-seen scalars only).
                safe_pol: dict[str, Any] = {
                    "htf_reeval": bool(sec_pol.get("htf_reeval")),
                    "gaps_supported": bool(sec_pol.get("gaps_supported")),
                    "lookahead_supported": bool(sec_pol.get("lookahead_supported")),
                    "calls": int(sec_pol.get("calls") or 0),
                    "notes": list(sec_pol.get("notes") or []),
                    "policies": {},
                }
                raw_pols = sec_pol.get("policies") or {}
                if isinstance(raw_pols, dict):
                    for tag, entry in raw_pols.items():
                        if not isinstance(entry, dict):
                            continue
                        safe_entry: dict[str, Any] = {}
                        for k, v in entry.items():
                            if isinstance(v, (str, int, float, bool)) or v is None:
                                safe_entry[k] = v
                            else:
                                safe_entry[k] = str(v)
                        safe_pol["policies"][str(tag)] = safe_entry
                meta_out["request_security"] = safe_pol
        except Exception:
            pass
        interpret_out: dict[str, Any] = {
            "plots": final_series,
            "series": series_map,
            "plot_meta": plot_meta,
            "events": all_events,
            "drawings": drawings,
            "alerts": alerts,
            "inputs": input_defs,
            "count": n_result_bars,
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "interpret",
            "overlay": overlay,
            "script_name": script_name,
            "script_type": script_type,
            "meta": meta_out,
        }
        if alert_conditions:
            interpret_out["alert_conditions"] = alert_conditions
        if timed_out:
            interpret_out["timed_out"] = True
            interpret_out["error"] = "Script execution timed out"
            interpret_out["error_kind"] = ERROR_KIND_RUNTIME
        return _attach_logs_profile(
            interpret_out,
            total_ms=total_ms,
            bars=n_result_bars,
            mode="interpret",
            parse_ms=parse_ms,
            eval_ms=eval_ms,
            lines=line_rows,
        )

    @staticmethod
    def _compile_eligible(source_code: str) -> tuple[bool, str]:
        """Cheap prefilter before attempting compile (auto mode).

        Returns ``(eligible, reason_if_not)``.

        Numba is **not** required for eligibility: object-mode scripts (strategy,
        UDT, map/array heavy) compile to a pure-Python bar loop. Missing Numba
        only fails pure-numeric emit inside ``compile_script`` (auto caches that
        failure for subsequent runs of the same source).
        """
        global _HAS_COMPILER
        if _HAS_COMPILER is False:
            return False, "compiler package unavailable"
        if _HAS_COMPILER is None:
            try:
                import pynescript.compiler.engine  # noqa: F401

                _HAS_COMPILER = True
            except ImportError:
                _HAS_COMPILER = False
                return False, "compiler package unavailable"
        src = source_code or ""
        # Import / request.* need interpreter library + data plumbing
        if re.search(r"(?m)^\s*import\s+\S+", src):
            return False, "import statements not supported in compile path"
        if "request." in src:
            return False, "request.* not supported in compile path"
        return True, ""

    @staticmethod
    def _source_cache_key(source_code: str) -> str:
        return hashlib.sha256((source_code or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _is_cacheable_compile_failure(err: str) -> bool:
        """True for deterministic source/environment failures (not bar-data runtime)."""
        e = (err or "").strip()
        if not e:
            return False
        # Data-dependent execution failures must not poison auto forever.
        if e.startswith("Compiled Runtime Error"):
            return False
        if e.startswith("Compile Error"):
            return True
        if e.startswith("Compile mode unavailable"):
            return True
        low = e.lower()
        if "numba" in low and ("required" in low or "not installed" in low):
            return True
        return False

    @staticmethod
    def _remember_compile_failure(cache_key: str, reason: str) -> None:
        if not cache_key or not reason:
            return
        if len(_HOST_COMPILE_FAIL_CACHE) >= _HOST_COMPILE_FAIL_CACHE_MAX and cache_key not in _HOST_COMPILE_FAIL_CACHE:
            try:
                _HOST_COMPILE_FAIL_CACHE.pop(next(iter(_HOST_COMPILE_FAIL_CACHE)))
            except StopIteration:
                pass
        _HOST_COMPILE_FAIL_CACHE[cache_key] = reason

    def _run_auto(
        self,
        source_code: str,
        ohlcv_data: list[dict],
        data_feed=None,
        data_provider=None,
        inputs: dict | None = None,
        timeout_seconds: float | None = None,
        libraries: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Try compile; fall back to interpret on eligibility fail or any error.

        Sets ``auto_backend`` to ``compile`` or ``interpret``. On fallback, sets
        ``compile_fallback_reason`` to a stable human-readable string.

        **Does not** compare plot values and switch backends on mismatch — that
        would hide packing/kernel bugs. Value parity is measured by the harness
        with explicit ``mode=interpret`` vs ``mode=compile``.
        """
        # Compile path does not apply input.* overrides — prefer full host semantics.
        if inputs:
            result = self.run(
                source_code,
                ohlcv_data,
                data_feed=data_feed,
                data_provider=data_provider,
                mode="interpret",
                inputs=inputs,
                timeout_seconds=timeout_seconds,
                libraries=libraries,
            )
            if isinstance(result, dict):
                result["mode"] = result.get("mode") or "interpret"
                result["auto_backend"] = "interpret"
                result["compile_fallback_reason"] = "input.* overrides require interpret path"
            return result

        src_key = self._source_cache_key(source_code)
        prior_fail = _HOST_COMPILE_FAIL_CACHE.get(src_key)
        if prior_fail is not None:
            eligible, reason = False, prior_fail
        else:
            eligible, reason = self._compile_eligible(source_code)

        compile_err: str | None = reason or None
        if eligible:
            compiled_result = self._run_compiled(source_code, ohlcv_data)
            if "error" not in compiled_result:
                _HOST_COMPILE_FAIL_CACHE.pop(src_key, None)
                compiled_result["mode"] = "compile"
                compiled_result["auto_backend"] = "compile"
                return compiled_result
            compile_err = str(compiled_result.get("error") or "compile failed")
            if self._is_cacheable_compile_failure(compile_err):
                self._remember_compile_failure(src_key, compile_err)
        elif reason and self._is_cacheable_compile_failure(reason):
            self._remember_compile_failure(src_key, reason)

        # Interpret fallback (full host semantics)
        result = self.run(
            source_code,
            ohlcv_data,
            data_feed=data_feed,
            data_provider=data_provider,
            mode="interpret",
            inputs=inputs,
            timeout_seconds=timeout_seconds,
            libraries=libraries,
        )
        if isinstance(result, dict):
            result["mode"] = result.get("mode") or "interpret"
            result["auto_backend"] = "interpret"
            if compile_err:
                result["compile_fallback_reason"] = compile_err
        return result

    def _run_compiled(self, source_code: str, ohlcv_data: list[dict]) -> dict:
        """Execute via Numba numeric or pure-Python object-mode bar loop.

        Numba is required only for pure-numeric scripts; object-mode (strategy,
        collections, drawings) works without it. Host caches successful
        ``CompiledScript`` values by raw-source sha256.
        """
        t_total0 = time.perf_counter()
        _clear_pine_logger()
        n_bars_hint = len(ohlcv_data) if ohlcv_data else 0

        try:
            from pynescript.compiler.engine import compile_script
        except ImportError as e:
            return _attach_logs_profile(
                _error_payload(
                    _format_exc_message("Compile mode unavailable", e),
                    kind=ERROR_KIND_COMPILE,
                    exc=e,
                ),
                total_ms=(time.perf_counter() - t_total0) * 1000.0,
                bars=n_bars_hint,
                mode="compile",
            )

        if not ohlcv_data:
            return _attach_logs_profile(
                {"plots": [], "events": [], "count": 0, "mode": "compile", "series": {}},
                total_ms=(time.perf_counter() - t_total0) * 1000.0,
                bars=0,
                mode="compile",
            )

        # Host short-circuit: raw-source hash → CompiledScript (skips sanitize on hit).
        cache_key = self._source_cache_key(source_code)
        script_id = cache_key[:16]
        compiled = _HOST_COMPILE_CACHE.get(cache_key)
        was_cached = compiled is not None

        t_compile0 = time.perf_counter()
        if compiled is None:
            try:
                compiled = compile_script(source_code)
            except Exception as e:
                compile_ms = (time.perf_counter() - t_compile0) * 1000.0
                return _attach_logs_profile(
                    _error_payload(
                        _format_exc_message("Compile Error", e),
                        kind=ERROR_KIND_COMPILE,
                        exc=e,
                    ),
                    total_ms=(time.perf_counter() - t_total0) * 1000.0,
                    bars=n_bars_hint,
                    mode="compile",
                    parse_ms=compile_ms,
                    eval_ms=0.0,
                )
            if len(_HOST_COMPILE_CACHE) >= _HOST_COMPILE_CACHE_MAX:
                try:
                    _HOST_COMPILE_CACHE.pop(next(iter(_HOST_COMPILE_CACHE)))
                except StopIteration:
                    pass
            _HOST_COMPILE_CACHE[cache_key] = compiled
            _HOST_COMPILE_FAIL_CACHE.pop(cache_key, None)
        compile_ms = (time.perf_counter() - t_compile0) * 1000.0

        # Single-pass float64 packing — same defaults as interpret (_pack_ohlcv_columns).
        try:
            opens, highs, lows, closes, volumes, times = _ohlcv_pack_cached(ohlcv_data)
        except Exception as e:
            return _attach_logs_profile(
                _error_payload(
                    _format_exc_message("Data Error packing OHLCV", e),
                    kind=ERROR_KIND_DATA,
                    exc=e,
                ),
                total_ms=(time.perf_counter() - t_total0) * 1000.0,
                bars=n_bars_hint,
                mode="compile",
                parse_ms=compile_ms,
                eval_ms=0.0,
            )

        t_run0 = time.perf_counter()
        try:
            try:
                from pynescript.compiler.numba_builtins import set_chart_identity

                set_chart_identity(
                    ticker=getattr(self._syminfo, "ticker", None) or self.symbol,
                    tickerid=getattr(self._syminfo, "tickerid", None) or self.symbol,
                    prefix=getattr(self._syminfo, "prefix", "") or "",
                )
            except Exception:
                pass
            series_map = compiled.run(opens, highs, lows, closes, volumes, time=times)
        except Exception as e:
            run_ms = (time.perf_counter() - t_run0) * 1000.0
            return _attach_logs_profile(
                _error_payload(
                    _format_exc_message("Compiled Runtime Error", e),
                    kind=ERROR_KIND_RUNTIME,
                    exc=e,
                ),
                total_ms=(time.perf_counter() - t_total0) * 1000.0,
                bars=n_bars_hint,
                mode="compile",
                parse_ms=compile_ms,
                eval_ms=run_ms,
            )
        run_ms = (time.perf_counter() - t_run0) * 1000.0

        drawings: list[Any] = []
        events: list[Any] = []
        json_series: dict[str, list[Any]] = {}
        if isinstance(series_map, dict):
            # Read meta keys without mutating the map (safe if engine reuses dicts).
            drawings = series_map.get("__drawings", []) or []
            events = series_map.get("__events", []) or []

            # JSON-safe series map (numpy NaN → null). Dominant host wrap cost after pack.
            _to_json = _series_values_jsonable
            for k, v in series_map.items():
                ks = k if isinstance(k, str) else str(k)
                if ks.startswith("__"):
                    continue
                if type(ks) is str:
                    ks = intern(ks)
                json_series[ks] = _to_json(v)

        # Compile-path GC: __drawings is append-only; trim by declaration caps
        # parsed from source (defaults 50). Interpret path GCs in DrawingRegistry.
        drawing_limits: dict[str, int] = {
            "max_lines_count": 50,
            "max_labels_count": 50,
            "max_boxes_count": 50,
            "max_polylines_count": 50,
        }
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            _hard = {
                "max_lines_count": 500,
                "max_labels_count": 500,
                "max_boxes_count": 500,
                "max_polylines_count": 100,
            }
            for _key, _cap in _hard.items():
                _m = re.search(rf"\b{_key}\s*=\s*(\d+)", source_code or "")
                if _m:
                    try:
                        _n = int(_m.group(1))
                        drawing_limits[_key] = max(1, min(_cap, _n))
                    except (TypeError, ValueError):
                        pass
            if isinstance(drawings, list) and drawings:
                # Fold line.set_* / label.set_* onto handles before GC + JSON
                drawings = DrawingRegistry.fold_compile_drawing_mutations(drawings)
                drawings = DrawingRegistry.gc_exported_drawings(drawings, drawing_limits)
        except Exception:
            pass

        # Lift compile __drawings visual events (bgcolor/plotshape/plotchar/plotarrow)
        # into titled series keys so interpret↔compile key sets align (Agent 07 helper).
        header = _parse_script_header_fields(source_code)
        plot_meta = _compile_plot_meta(json_series)
        _stamp_compile_plot_kinds(plot_meta, compiled.plot_titles, compiled.plot_kinds)
        _n_visual = int(n_bars_hint or 0) or len(ohlcv_data or ())
        if isinstance(drawings, list) and drawings and _n_visual > 0:
            try:
                from pynescript.ast.evaluator.builtins.plotting import (
                    merge_visual_series_from_drawings,
                )

                merge_visual_series_from_drawings(
                    json_series,
                    drawings,
                    _n_visual,
                    plot_meta=plot_meta,
                )
            except Exception:
                pass
            # Geometry-only AXIS payload — same shape as interpret export_for_api.
            try:
                bar_times = [int(t or 0) for t in (times if times is not None else [])]
                drawings = DrawingRegistry.export_compile_events_for_api(drawings, bar_times)
            except Exception:
                drawings = []

        # Primary plot series (first numeric plot) as list for frontend compatibility
        final_series: list = next(iter(json_series.values()), []) if json_series else []

        # Stamp script/run ids on strategy events (skip when empty — pure indicators)
        if events:
            rid = self._run_id
            for ev in events:
                if isinstance(ev, dict):
                    ev.setdefault("script_id", script_id)
                    ev.setdefault("run_id", rid)

        # Series envelope parity with interpret: declaration fields.
        # Style/color for compile is best-effort (engine does not export per-plot meta).
        input_defs: list[dict[str, Any]] = []
        meta_out: dict[str, Any] = {
            "overlay": header["overlay"],
            "script_name": header["script_name"],
            "script_type": header["script_type"],
            "inputs": input_defs,
        }
        meta_out.update(drawing_limits)

        # Do NOT return generated_code by default — large scripts + cold Numba make
        # JSON responses multi-MB and can trip AXIS/gunicorn timeouts. Opt-in via
        # PYNESCRIPT_RETURN_GENERATED_CODE=1 for debugging.
        # Compile path does not execute interpret-only alert() side effects yet
        out: dict[str, Any] = {
            "plots": final_series,
            "series": json_series,
            "plot_meta": plot_meta,
            "drawings": drawings if isinstance(drawings, list) else list(drawings or []),
            "events": events if isinstance(events, list) else list(events or []),
            "alerts": [],
            "inputs": input_defs,
            "count": len(ohlcv_data),
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "compile",
            "object_mode": compiled.object_mode,
            "overlay": header["overlay"],
            "script_name": header["script_name"],
            "script_type": header["script_type"],
            "compile_ms": round(compile_ms, 2),
            "run_ms": round(run_ms, 2),
            "compile_cached": was_cached,
            "meta": meta_out,
        }
        # Engine nopython → object recovery (still compile backend; not interpret fallback)
        nopython_reason = getattr(compiled, "nopython_fallback_reason", None)
        if nopython_reason:
            out["nopython_fallback_reason"] = nopython_reason
        if os.environ.get("PYNESCRIPT_RETURN_GENERATED_CODE", "").strip() in {"1", "true", "yes"}:
            out["generated_code"] = compiled.generated_code
        # Best-effort: map compile → parse_ms, bar loop → eval_ms.
        return _attach_logs_profile(
            out,
            total_ms=(time.perf_counter() - t_total0) * 1000.0,
            bars=len(ohlcv_data),
            mode="compile",
            parse_ms=compile_ms,
            eval_ms=run_ms,
        )
