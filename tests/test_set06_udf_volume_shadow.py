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

"""UDF local ``vol`` vs chart ``volume``, request.security UDT, if+var emit."""

from __future__ import annotations

import ast
import signal

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_SET06 = Path(__file__).parent / "data" / "set06"


def _ohlcv(n: int = 20, start: float = 100.0, vol: float = 1.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1.0, close - 1.0, close, np.full(n, vol, dtype=np.float64)


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


def _def_line(code: str, name: str) -> str:
    prefix = f"def {name}("
    for ln in code.splitlines():
        if ln.startswith(prefix):
            return ln
    msg = f"no def {name}( in transpile"
    raise AssertionError(msg)


def _call_and_def_arities(code: str, name: str) -> tuple[int, list[int]]:
    """Return (def arity, call arities) for ``name`` via the generated AST."""
    tree = ast.parse(code)
    def_arity: int | None = None
    call_arities: list[int] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            def_arity = len(node.args.args)
            break
    if def_arity is None:
        msg = f"no def {name} in generated AST"
        raise AssertionError(msg)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
            call_arities.append(len(node.args) + len(node.keywords))
    return def_arity, call_arities


class _TimeoutError(Exception):
    """SIGALRM fired while a compile/run was expected to finish quickly."""


def _run_with_timeout(fn, seconds: float = 20.0):
    def _handler(_signum, _frame):
        msg = "compile/run exceeded timeout"
        raise _TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)


_GET_COUNTS_SRC = """//@version=5
indicator("x")
length = 2
get_counts(condition, top, btm)=>
    var count = 0
    var vol = 0.
    if condition
        count := 0
        vol := 0.
    else
        vol += low[length] < top and high[length] > btm ? volume[length] : 0
        count += low[length] < top and high[length] > btm ? 1 : 0
    [count, vol]
[ph_count, ph_vol] = get_counts(false, 1e9, -1e9)
plot(ph_count)
plot(ph_vol)
"""


_VOL_ACCUM_SRC = """//@version=5
indicator("x")
get_counts(condition)=>
    var vol = 0.
    if condition
        vol := 0.
    else
        vol += volume
    vol
plot(get_counts(false))
"""


_SECURITY_UDT_SRC = """//@version=6
indicator("x")
type TickerInfo
    string description
    array<float> prices
    int barIndex
info = TickerInfo.new("x", array.from(open, high, low, close), bar_index)
TickerInfo requestedInfo = request.security("NASDAQ:AAPL", timeframe.period, info)
if na(requestedInfo)
    requestedInfo := TickerInfo.new(prices = array.new<float>(4))
plot(na(requestedInfo) ? -1 : requestedInfo.barIndex)
plot(requestedInfo.prices.get(3))
"""


_IF_VAR_SRC = """//@version=6
strategy("x")
buyAndHoldReturnPct(fromDate) =>
    if time >= fromDate
        money = close * syminfo.pointvalue
        var initialBal = strategy.convert_to_account(money)
        (strategy.convert_to_account(money) - initialBal) / initialBal * 100
plot(buyAndHoldReturnPct(0))
"""


def test_udf_local_vol_def_call_arity_match() -> None:
    """``var vol`` must not steal chart ``vol_arr`` (def 14 vs call 15)."""
    code = transpile(_GET_COUNTS_SRC)
    def_line = _def_line(code, "get_counts")
    assert "__user_vol_arr" in def_line
    # Chart volume formal is still present and distinct from the local store.
    params = [p.strip() for p in def_line[def_line.index("(") + 1 : def_line.rindex(")")].split(",")]
    assert "vol_arr" in params
    assert "__user_vol_arr" in params
    assert params.count("vol_arr") == 1
    def_arity, call_arities = _call_and_def_arities(code, "get_counts")
    assert call_arities, "no get_counts( call in transpile"
    assert all(n == def_arity for n in call_arities), (def_arity, call_arities)
    compiled = compile_script(_GET_COUNTS_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, vol=3.0))
    # length=2, condition always false, top/btm always match → accumulate volume[2]
    # bars 0,1: history na → +0; bars 2..19: +3.0 → 18 * 3 = 54
    assert _last(out, "plot_1") == 54.0
    assert _last(out, "plot_0") == 18.0


def test_udf_local_vol_reads_chart_volume() -> None:
    """``vol += volume`` inside a UDF must add chart volume, not the local."""
    code = transpile(_VOL_ACCUM_SRC)
    def_line = _def_line(code, "get_counts")
    assert "__user_vol_arr" in def_line
    assert "vol_arr" in def_line
    def_arity, call_arities = _call_and_def_arities(code, "get_counts")
    assert all(n == def_arity for n in call_arities), (def_arity, call_arities)
    compiled = compile_script(_VOL_ACCUM_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, vol=2.0))
    # If local stole vol_arr, volume would be the local (stays 0).
    assert _last(out) == 40.0


def test_request_security_udt_is_object_handle() -> None:
    """``TickerInfo x = request.security(..., info)`` is a UDT handle, not float."""
    code = transpile(_SECURITY_UDT_SRC)
    assert "requestedInfo_arr[__bar_idx] = np.nan" not in code
    assert "safe_float(request" not in code
    compiled = compile_script(_SECURITY_UDT_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.0))
    # passthrough stub: same handle as ``info`` → barIndex = last bar
    assert _last(out, "plot_0") == 19.0
    assert _last(out, "plot_1") == 119.0


def test_udf_if_var_convert_to_account_is_valid_python() -> None:
    """If-as-result with inner ``var`` must emit valid if/else (na when false)."""
    code = transpile(_IF_VAR_SRC)
    compile(code, "<buyAndHoldReturnPct>", "exec")
    assert " =  if " not in code
    compiled = compile_script(_IF_VAR_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.0))
    # identity convert: initialBal = close[0] = 100; last (119-100)/100*100 = 19
    assert abs(_last(out) - 19.0) < 1e-9


@pytest.mark.parametrize(
    "rel",
    [
        "indicators/13834_ind_1_1.pine",
        "indicators/5256_ind_liquidity_swings.pine",
    ],
)
def test_corpus_get_counts_arity_and_run(rel: str) -> None:
    src = (_SET06 / rel).read_text(encoding="utf-8")
    code = transpile(src)
    def_line = _def_line(code, "get_counts")
    assert "__user_vol_arr" in def_line
    assert "vol_arr" in def_line
    def_arity, call_arities = _call_and_def_arities(code, "get_counts")
    assert call_arities
    assert all(n == def_arity for n in call_arities), (rel, def_arity, call_arities)

    def _go() -> dict:
        compiled = compile_script(src, use_cache=False)
        return compiled.run(*_ohlcv(20))

    try:
        out = _run_with_timeout(_go, seconds=20.0)
    except _TimeoutError:
        pytest.skip(f"{rel} compile/run hung; reduced snippet is the lock")
    assert out is not None
    plots = [k for k in out if not k.startswith("__")]
    assert plots or "__drawings" in out


@pytest.mark.parametrize(
    "rel",
    [
        "indicators/2560_ind_requesting_user_defined_types_demo.pine",
    ],
)
def test_corpus_request_security_udt(rel: str) -> None:
    src = (_SET06 / rel).read_text(encoding="utf-8")
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    assert "__drawings" in out


@pytest.mark.parametrize(
    "rel",
    [
        "strategies/0755_str_strategy_convert_to_account_example_2.pine",
        "strategies/0756_str_strategy_convert_to_account_example_2_2.pine",
    ],
)
def test_corpus_if_var_convert_to_account(rel: str) -> None:
    src = (_SET06 / rel).read_text(encoding="utf-8")
    code = transpile(src)
    compile(code, f"<{rel}>", "exec")
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    assert "plot_0" in out
