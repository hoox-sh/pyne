# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: bare numeric input type tokens stay numeric; string/color stay object."""

from __future__ import annotations

# ruff: noqa: S101, T201
from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime

BARS = [
    {
        "open": 100.0 + i,
        "high": 101.0 + i,
        "low": 99.0 + i,
        "close": 100.5 + i,
        "volume": 1000.0,
        "time": 1_700_000_000_000 + i * 60_000,
    }
    for i in range(20)
]

NUMERIC = """//@version=5
indicator("x")
a = input(3, type=input.integer)
b = input(2.0, type=input.float)
flag = input(true, type=input.bool)
plot(ta.sma(close, a) * b, title="p")
plot(flag ? 1 : 0, title="q")
"""

SOURCE = """//@version=5
indicator("x")
s = input(close, type=input.source)
plot(s, title="s")
"""

STRING = """//@version=5
indicator("x")
s = input("hi", type=input.string)
plot(close, title="p")
"""

COLOR = """//@version=5
indicator("x")
c = input(color.red, type=input.color)
plot(close, title="p", color=c)
"""


def _same(actual, expected) -> None:
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        if want is None or (isinstance(want, float) and want != want):
            assert got is None or (isinstance(got, float) and got != got), (got, want)
        else:
            assert abs(float(got) - float(want)) < 1e-9, (got, want)


def main() -> None:
    compiled = compile_script(NUMERIC, use_cache=False)
    assert compiled.object_mode is False
    interp = Runtime(symbol="TEST").run(NUMERIC, BARS, mode="interpret")
    out = Runtime(symbol="TEST").run(NUMERIC, BARS, mode="compile")
    assert "error" not in interp, interp.get("error")
    assert "error" not in out, out.get("error")
    _same(out["series"]["p"], interp["series"]["p"])
    _same(out["series"]["q"], interp["series"]["q"])

    source = compile_script(SOURCE, use_cache=False)
    assert source.object_mode is False
    src_out = Runtime(symbol="TEST").run(SOURCE, BARS, mode="compile")
    assert "error" not in src_out, src_out.get("error")
    _same(src_out["series"]["s"], [float(b["close"]) for b in BARS])

    assert compile_script(STRING, use_cache=False).object_mode is True
    assert compile_script(COLOR, use_cache=False).object_mode is True

    print("INPUT_TOKEN_OK int=1 float=1 bool=1 source=1 string=object color=object")


if __name__ == "__main__":
    main()
