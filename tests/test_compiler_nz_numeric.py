# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""nz() over numeric params/locals stays on the nopython path."""

from __future__ import annotations

import pytest

from pynescript.compiler import engine
from pynescript.runtime import Runtime


@pytest.fixture(autouse=True)
def _fresh_compile_cache(monkeypatch: pytest.MonkeyPatch):
    """Do not reuse a pre-fix object-mode module for the same source."""
    monkeypatch.setenv("PYNE_COMPILE_DISK_CACHE", "0")
    engine.clear_compile_cache()
    yield
    engine.clear_compile_cache()


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

_SRC_LOCAL = """//@version=6
indicator("nz local")
f(float src) =>
    x = src * 2.0
    nz(x)
plot(f(close), "x")
"""

_SRC_HIST = """//@version=6
indicator("nz param history")
f(float src) =>
    nz(src[1])
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


def _run(src: str, mode: str = "compile") -> dict[str, object]:
    return Runtime(symbol="TEST").run(src, _bars(), mode=mode)


def test_nz_numeric_param_stays_numeric() -> None:
    out = _run(_SRC_PARAM)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    interp = _run(_SRC_PARAM, mode="interpret")
    assert "error" not in interp, interp.get("error")
    assert out["series"] == interp["series"]


def test_nz_numeric_param_replacement_handles_nan() -> None:
    out = _run(_SRC_PARAM_REPL)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    assert out["series"]["nan"] == [5.0, 5.0, 5.0, 5.0]


def test_nz_numeric_local_from_param_stays_numeric() -> None:
    out = _run(_SRC_LOCAL)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [201.0, 203.0, 205.0, 207.0]
    interp = _run(_SRC_LOCAL, mode="interpret")
    assert "error" not in interp, interp.get("error")
    assert out["series"] == interp["series"]


def test_nz_numeric_param_history_stays_numeric() -> None:
    out = _run(_SRC_HIST)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [0.0, 100.5, 101.5, 102.5]
    interp = _run(_SRC_HIST, mode="interpret")
    assert "error" not in interp, interp.get("error")
    assert out["series"] == interp["series"]


def test_nz_series_still_numeric() -> None:
    out = _run(_SRC_SERIES)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]


def test_nz_string_local_replacement_stays_object() -> None:
    out = _run(_SRC_STRING_LOCAL_REPL)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is True
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    interp = _run(_SRC_STRING_LOCAL_REPL, mode="interpret")
    assert out["series"] == interp["series"]
    code = engine._transpile_once(_SRC_STRING_LOCAL_REPL)[0]
    assert "nz_py(" in code
    assert "numba_nz(" not in code


def test_nz_string_param_replacement_stays_object() -> None:
    out = _run(_SRC_STRING_PARAM_REPL)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is True
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    interp = _run(_SRC_STRING_PARAM_REPL, mode="interpret")
    assert out["series"] == interp["series"]
    code = engine._transpile_once(_SRC_STRING_PARAM_REPL)[0]
    assert "nz_py(" in code
    assert "numba_nz(" not in code


def test_nz_numeric_local_replacement_stays_numeric() -> None:
    out = _run(_SRC_NUMERIC_LOCAL_REPL)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is False
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
    code = engine._transpile_once(_SRC_NUMERIC_LOCAL_REPL)[0]
    assert "numba_nz(" in code


def test_nz_string_param_stays_object() -> None:
    out = _run(_SRC_STRING)
    assert "error" not in out, out.get("error")
    assert out["object_mode"] is True
    assert out["series"]["x"] == [100.5, 101.5, 102.5, 103.5]
