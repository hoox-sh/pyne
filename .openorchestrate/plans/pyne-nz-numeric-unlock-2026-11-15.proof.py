# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: nz() over numeric params/locals stays on the nopython path."""

# ruff: noqa: S101, T201

from __future__ import annotations

import os

from typing import Any

from pynescript.compiler import engine
from pynescript.runtime import Runtime


# The disk cache may hold a pre-fix object-mode module for the same source.
os.environ["PYNE_COMPILE_DISK_CACHE"] = "0"


_SRC_PARAM = """//@version=6
indicator("nz param")
f(float src) =>
    nz(src)
plot(f(close), "x")
"""

_SRC_PARAM_REPL = """//@version=6
indicator("nz param repl")
f(float src) =>
    nz(src, 5.0)
plot(f(close), "x")
plot(f(na), "nan")
"""

_SRC_HIST = """//@version=6
indicator("nz param history")
f(float src) =>
    nz(src[1])
plot(f(close), "x")
"""

_SRC_LOCAL = """//@version=6
indicator("nz local")
f(float src) =>
    x = src * 2.0
    nz(x)
plot(f(close), "x")
"""

_SRC_SERIES = """//@version=6
indicator("nz series")
plot(nz(close), "x")
"""

_SRC_STRING = """//@version=6
indicator("nz string")
f(string s) =>
    nz(s, "x")
plot(close, "x")
"""

_SRC_STRING_LOCAL_REPL = """//@version=6
indicator("nz string local repl")
f(float src) =>
    s = "x"
    nz(src, s)
plot(f(close), "x")
"""

_SRC_STRING_PARAM_REPL = """//@version=6
indicator("nz string param repl")
f(string s) =>
    nz(close, s)
plot(f("x"), "x")
"""

_SRC_NUMERIC_LOCAL_REPL = """//@version=6
indicator("nz numeric local repl")
f(float src) =>
    k = 5.0
    nz(src, k)
plot(f(close), "x")
"""


def _bars(n: int = 4) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def _run(src: str, mode: str = "compile") -> dict[str, Any]:
    engine.clear_compile_cache()
    return Runtime(symbol="TEST").run(src, _bars(), mode=mode)


def main() -> None:
    # 1. Typed numeric param.
    param = _run(_SRC_PARAM)
    assert "error" not in param, param.get("error")
    assert param["object_mode"] is False
    assert param["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    interp = _run(_SRC_PARAM, mode="interpret")
    assert param["series"] == interp["series"]

    # 2. Replacement + NaN on the nopython path.
    repl = _run(_SRC_PARAM_REPL)
    assert "error" not in repl, repl.get("error")
    assert repl["object_mode"] is False
    assert repl["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    assert repl["series"]["nan"] == [5.0, 5.0, 5.0, 5.0]

    # 3. Param history load.
    hist = _run(_SRC_HIST)
    assert "error" not in hist, hist.get("error")
    assert hist["object_mode"] is False
    assert hist["series"]["x"] == [0.0, 100.5, 101.5, 102.5]

    # 4. Numeric local derived from a numeric param.
    local = _run(_SRC_LOCAL)
    assert "error" not in local, local.get("error")
    assert local["object_mode"] is False
    assert local["series"]["x"] == [201.0, 203.0, 205.0, 207.0]

    # 5. Regressions: series arg stays numeric; string param stays object.
    series = _run(_SRC_SERIES)
    assert "error" not in series, series.get("error")
    assert series["object_mode"] is False
    assert series["series"]["x"] == [100.5, 101.5, 102.5, 103.5]

    string = _run(_SRC_STRING)
    assert "error" not in string, string.get("error")
    assert string["object_mode"] is True
    assert string["series"]["x"] == [100.5, 101.5, 102.5, 103.5]

    # 6. String replacement (local and param) keeps object mode / nz_py.
    for str_src in (_SRC_STRING_LOCAL_REPL, _SRC_STRING_PARAM_REPL):
        str_out = _run(str_src)
        assert "error" not in str_out, str_out.get("error")
        assert str_out["object_mode"] is True
        assert str_out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
        code = engine._transpile_once(str_src)[0]
        assert "nz_py(" in code
        assert "numba_nz(" not in code

    # 7. Numeric local replacement stays numeric.
    num_repl = _run(_SRC_NUMERIC_LOCAL_REPL)
    assert "error" not in num_repl, num_repl.get("error")
    assert num_repl["object_mode"] is False
    assert num_repl["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    assert "numba_nz(" in engine._transpile_once(_SRC_NUMERIC_LOCAL_REPL)[0]

    print(
        "NZ_NUMERIC_OK param=100.5 repl=100.5 nan=5.0 hist=100.5 "
        "local=201.0 series=100.5 string=1 str_local=1 str_param=1 num_local_repl=100.5"
    )


if __name__ == "__main__":
    main()
