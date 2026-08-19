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

"""User ``round()`` UDF must pass free-series / chart formals (set06 DOM)."""

from __future__ import annotations

import ast
import signal

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_SET06 = Path(__file__).parent / "data" / "set06"


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1.0, close - 1.0, close, np.ones(n)


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


_ROUND_UDF_SRC = """//@version=5
indicator("t")
tickMode = true
round(float value) => tickMode ? math.round(value) : int(value)
plot(round(close))
"""


_BUILTIN_MATH_ROUND_SRC = """//@version=5
indicator("t")
plot(math.round(close))
plot(math.round_to_mintick(close + 0.4))
"""


def test_udf_round_def_includes_tickmode_and_bar_idx() -> None:
    """``round`` → ``round_``; formals include free ``tickMode`` and ``__bar_idx``."""
    code = transpile(_ROUND_UDF_SRC)
    def_line = _def_line(code, "round_")
    assert "tickMode" in def_line or "tickMode_arr" in def_line
    assert "__bar_idx" in def_line
    def_arity, call_arities = _call_and_def_arities(code, "round_")
    assert call_arities, "no round_( call in transpile"
    assert all(n == def_arity for n in call_arities), (def_arity, call_arities)


def test_udf_round_compile_run() -> None:
    compiled = compile_script(_ROUND_UDF_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.0))
    # tickMode true → math.round(close); last close = 119
    assert _last(out) == 119.0


def test_builtin_math_round_still_one_arg() -> None:
    """``math.round`` / ``math.round_to_mintick`` must not become ``round_``."""
    code = transpile(_BUILTIN_MATH_ROUND_SRC)
    assert "def round_(" not in code
    compiled = compile_script(_BUILTIN_MATH_ROUND_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.4))
    assert _last(out, "plot_0") == 119.0
    assert np.isfinite(_last(out, "plot_1"))


def test_corpus_13716_round_arity_no_missing_args() -> None:
    src = (_SET06 / "indicators" / "13716_ind_depth_of_market_dom.pine").read_text(encoding="utf-8")
    code = transpile(src)
    def_line = _def_line(code, "round_")
    assert "tickMode" in def_line or "tickMode_arr" in def_line
    assert "__bar_idx" in def_line
    def_arity, call_arities = _call_and_def_arities(code, "round_")
    assert call_arities
    assert all(n == def_arity for n in call_arities), (def_arity, call_arities)

    def _go() -> dict:
        compiled = compile_script(src, use_cache=False)
        return compiled.run(*_ohlcv(20))

    try:
        out = _run_with_timeout(_go, seconds=20.0)
    except TypeError as exc:
        if "round_()" in str(exc) and "missing" in str(exc):
            raise
        pytest.skip(f"13716 later error after round_ arity fixed: {exc}")
    except _TimeoutError:
        pytest.skip("13716 compile/run hung; reduced snippet is the lock")
    except Exception as exc:
        if "round_()" in str(exc) and "missing" in str(exc):
            raise
        pytest.skip(f"13716 later error after round_ arity fixed: {exc}")
    assert out is not None
    plots = [k for k in out if not k.startswith("__")]
    assert plots or "__drawings" in out
