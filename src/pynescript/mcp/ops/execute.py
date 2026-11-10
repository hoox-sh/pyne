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

"""Runtime.execute with caller OHLCV, plus interpret/compile last-value parity."""

from __future__ import annotations

import math
import time

from typing import Any

from pynescript.mcp.ops.common import load_source
from pynescript.mcp.ops.common import parse_error_fields
from pynescript.mcp.ops.common import synthetic_ohlcv_rows
from pynescript.mcp.serialize import BARS_MAX
from pynescript.mcp.serialize import clamp_bars
from pynescript.mcp.serialize import clamp_timeout
from pynescript.mcp.serialize import fail
from pynescript.mcp.serialize import jsonable
from pynescript.mcp.serialize import ok
from pynescript.mcp.serialize import split_plots


_RTOL = 1e-5
_ATOL = 1e-6


def _rows(ohlcv: list[dict[str, Any]] | None, bars: int) -> list[dict[str, Any]] | dict[str, Any]:
    if ohlcv:
        if len(ohlcv) > BARS_MAX:
            return fail(f"ohlcv length cap is {BARS_MAX}", kind="io")
        if len(ohlcv) < 2:
            return fail("ohlcv must have at least 2 bars", kind="io")
        return ohlcv
    return synthetic_ohlcv_rows(clamp_bars(bars))


def execute_source(
    source: str | None = None,
    path: str | None = None,
    *,
    encoding: str = "utf-8",
    ohlcv: list[dict[str, Any]] | None = None,
    bars: int = 50,
    mode: str = "auto",
    inputs: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
    sample: int = 8,
    include_trades: bool = False,
    ticker: str = "MCP",
    timeframe: str = "1m",
) -> dict[str, Any]:
    """Run Pine through :class:`~pynescript.runtime.Runtime`."""
    from pynescript.ast.evaluator.builtins.timeframe import to_pine_period
    from pynescript.runtime import Runtime

    loaded = load_source(source, path, encoding=encoding)
    if isinstance(loaded, dict):
        return loaded
    text, label = loaded
    rows = _rows(ohlcv, bars)
    if isinstance(rows, dict):
        return rows
    mode_norm = (mode or "auto").strip().lower()
    if mode_norm not in ("interpret", "compile", "auto"):
        return fail("mode must be interpret, compile, or auto", kind="io")
    timeout = clamp_timeout(timeout_seconds)
    host = Runtime(symbol=ticker, timeframe=to_pine_period(timeframe))
    t0 = time.perf_counter()
    try:
        result = host.run(
            text,
            rows,
            mode=mode_norm,
            inputs=inputs,
            timeout_seconds=timeout,
        )
    except Exception as exc:
        fields = parse_error_fields(exc)
        return fail(
            f"{type(exc).__name__}: {fields.get('error') or exc}",
            kind="runtime",
            line=fields.get("line"),
            column=fields.get("column"),
            file=label,
        )
    elapsed = (time.perf_counter() - t0) * 1000
    if not isinstance(result, dict):
        return fail("runtime returned a non-object result", kind="runtime", file=label)
    if result.get("error"):
        return fail(
            str(result.get("error")),
            kind=str(result.get("error_kind") or "runtime"),
            file=label,
            extras=jsonable({k: v for k, v in result.items() if k != "error"}),
            elapsed_ms=round(elapsed, 2),
        )
    plots, extras = split_plots(result, sample=sample, include_trades=include_trades)
    return ok(
        file=label,
        bars=len(rows),
        mode=mode_norm,
        auto_backend=result.get("auto_backend"),
        compile_fallback_reason=result.get("compile_fallback_reason"),
        timed_out=bool(result.get("timed_out")),
        elapsed_ms=round(elapsed, 2),
        plots=plots,
        extras=extras,
        ticker=ticker,
        timeframe=timeframe,
    )


def _last_numeric(series: Any) -> float | None:
    try:
        if series is None:
            return None
        if isinstance(series, dict) and "last" in series:
            val = series["last"]
        elif hasattr(series, "__getitem__") and hasattr(series, "__len__") and len(series):
            val = series[-1]
        else:
            val = series
        if val is None:
            return None
        item = getattr(val, "item", None)
        if callable(item):
            val = item()
        num = float(val)
        if not math.isfinite(num):
            return None
        return num
    except Exception:
        return None


def _close(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(a, b, rel_tol=_RTOL, abs_tol=_ATOL)


def parity_source(
    source: str | None = None,
    path: str | None = None,
    *,
    encoding: str = "utf-8",
    ohlcv: list[dict[str, Any]] | None = None,
    bars: int = 50,
    timeout_seconds: float | None = None,
    ticker: str = "MCP",
    timeframe: str = "1m",
) -> dict[str, Any]:
    """Compare interpret vs compile last plot values (nan-aware allclose)."""
    loaded = load_source(source, path, encoding=encoding)
    if isinstance(loaded, dict):
        return loaded
    text, label = loaded
    rows = _rows(ohlcv, bars)
    if isinstance(rows, dict):
        return rows
    timeout = clamp_timeout(timeout_seconds)
    interp = execute_source(
        text,
        encoding=encoding,
        ohlcv=rows,
        mode="interpret",
        timeout_seconds=timeout,
        ticker=ticker,
        timeframe=timeframe,
        sample=1,
    )
    compiled = execute_source(
        text,
        encoding=encoding,
        ohlcv=rows,
        mode="compile",
        timeout_seconds=timeout,
        ticker=ticker,
        timeframe=timeframe,
        sample=1,
    )
    if not interp.get("ok"):
        return fail(
            str(interp.get("error") or "interpret failed"),
            kind="runtime",
            interpret=interp,
            compile=compiled,
            file=label,
        )
    if not compiled.get("ok"):
        return fail(
            str(compiled.get("error") or "compile failed"),
            kind="compile",
            interpret=interp,
            compile=compiled,
            file=label,
        )
    left = interp.get("plots") or {}
    right = compiled.get("plots") or {}
    names = sorted(set(left) | set(right))
    mismatches: list[dict[str, Any]] = []
    for name in names:
        a = _last_numeric(left.get(name))
        b = _last_numeric(right.get(name))
        if not _close(a, b):
            mismatches.append({"plot": name, "interpret": a, "compile": b})
    return ok(
        file=label,
        bars=len(rows),
        match=not mismatches,
        mismatches=mismatches,
        interpret_ms=interp.get("elapsed_ms"),
        compile_ms=compiled.get("elapsed_ms"),
        compile_fallback_reason=compiled.get("compile_fallback_reason"),
        auto_backend=compiled.get("auto_backend"),
    )
